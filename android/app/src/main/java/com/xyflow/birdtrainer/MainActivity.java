package com.xyflow.birdtrainer;

import android.app.Activity;
import android.content.SharedPreferences;
import android.content.res.AssetFileDescriptor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.media.MediaPlayer;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.Set;

public class MainActivity extends Activity {
    private final Random random = new Random();
    private final ArrayList<Clip> clips = new ArrayList<>();
    private final ArrayList<Button> answerButtons = new ArrayList<>();

    private LinearLayout root;
    private TextView title;
    private TextView subtitle;
    private TextView prompt;
    private TextView reveal;
    private TextView progress;
    private Button playButton;
    private Button nextButton;
    private Clip currentClip;
    private int selectedSpeciesId = -1;
    private int speciesCount = 0;
    private MediaPlayer player;
    private SharedPreferences prefs;

    private static final int INK = Color.rgb(29, 37, 40);
    private static final int MUTED = Color.rgb(96, 111, 116);
    private static final int PAGE = Color.rgb(244, 242, 236);
    private static final int PANEL = Color.WHITE;
    private static final int ACCENT = Color.rgb(23, 107, 91);
    private static final int RUST = Color.rgb(157, 79, 50);
    private static final int LINE = Color.rgb(217, 224, 223);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("progress", MODE_PRIVATE);
        loadDataset();
        buildUi();
        nextQuestion();
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopAudio();
    }

    private void loadDataset() {
        try {
            JSONObject dataset = new JSONObject(readAsset("dataset.json"));
            JSONArray items = dataset.getJSONArray("clips");
            for (int i = 0; i < items.length(); i++) {
                JSONObject item = items.getJSONObject(i);
                clips.add(new Clip(item));
            }
            speciesCount = dataset.optInt("speciesCount", countUniqueSpecies());
        } catch (Exception exception) {
            throw new RuntimeException("Unable to load bundled bird dataset", exception);
        }
    }

    private int countUniqueSpecies() {
        Set<Integer> seen = new HashSet<>();
        for (Clip clip : clips) {
            seen.add(clip.speciesId);
        }
        return seen.size();
    }

    private String readAsset(String name) throws Exception {
        try (InputStream input = getAssets().open(name);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) != -1) {
                output.write(buffer, 0, read);
            }
            return output.toString("UTF-8");
        }
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(PAGE);

        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(18), dp(18), dp(28));
        scroll.addView(root);

        title = text("Bird Sound Trainer", 28, Typeface.BOLD, INK);
        subtitle = text("Northeast / Ohio Valley pack", 15, Typeface.NORMAL, MUTED);
        root.addView(title);
        root.addView(subtitle);
        root.addView(spacer(16));

        progress = text("", 14, Typeface.BOLD, ACCENT);
        progress.setGravity(Gravity.CENTER);
        progress.setPadding(dp(10), dp(10), dp(10), dp(10));
        progress.setBackground(panelBackground(ACCENT, 0x18));
        root.addView(progress);
        root.addView(spacer(12));

        LinearLayout card = panel();
        prompt = text("Listen to the clip, then choose the bird.", 18, Typeface.BOLD, INK);
        reveal = text("", 14, Typeface.NORMAL, MUTED);
        reveal.setVisibility(View.GONE);
        playButton = primaryButton("Play Clip");
        playButton.setOnClickListener(view -> playCurrentClip());
        nextButton = secondaryButton("Next Bird");
        nextButton.setOnClickListener(view -> nextQuestion());

        card.addView(prompt);
        card.addView(spacer(10));
        card.addView(playButton);
        card.addView(spacer(10));
        card.addView(nextButton);
        card.addView(spacer(12));
        card.addView(reveal);
        root.addView(card);
        root.addView(spacer(14));

        for (int i = 0; i < 3; i++) {
            Button answer = answerButton();
            final Button chosen = answer;
            answer.setOnClickListener(view -> chooseAnswer(chosen));
            answerButtons.add(answer);
            root.addView(answer);
            root.addView(spacer(10));
        }

        TextView footer = text("20-second real Xeno-canto clips. Attribution appears after each answer.", 12, Typeface.NORMAL, MUTED);
        footer.setGravity(Gravity.CENTER);
        root.addView(spacer(8));
        root.addView(footer);
        setContentView(scroll);
    }

    private void nextQuestion() {
        stopAudio();
        selectedSpeciesId = -1;
        reveal.setVisibility(View.GONE);
        currentClip = pickClip();
        ArrayList<Clip> options = buildOptions(currentClip);
        for (int i = 0; i < answerButtons.size(); i++) {
            Clip option = options.get(i);
            Button button = answerButtons.get(i);
            button.setTag(option);
            button.setText(option.commonName + "\n" + option.scientificName);
            button.setTextColor(INK);
            button.setBackground(panelBackground(LINE, 0xFF));
            button.setEnabled(true);
        }
        prompt.setText("Which bird is this?");
        updateProgress();
    }

    private Clip pickClip() {
        if (clips.isEmpty()) {
            throw new IllegalStateException("No clips bundled");
        }
        return clips.get(random.nextInt(clips.size()));
    }

    private ArrayList<Clip> buildOptions(Clip answer) {
        ArrayList<Clip> sameFamily = new ArrayList<>();
        ArrayList<Clip> others = new ArrayList<>();
        Set<Integer> seen = new HashSet<>();
        seen.add(answer.speciesId);
        for (Clip clip : clips) {
            if (clip.speciesId == answer.speciesId) continue;
            if (clip.family.equals(answer.family)) {
                sameFamily.add(clip);
            } else {
                others.add(clip);
            }
        }
        Collections.shuffle(sameFamily, random);
        Collections.shuffle(others, random);

        ArrayList<Clip> options = new ArrayList<>();
        options.add(answer);
        addUniqueOptions(options, sameFamily, seen);
        addUniqueOptions(options, others, seen);
        while (options.size() > 3) {
            options.remove(options.size() - 1);
        }
        Collections.shuffle(options, random);
        return options;
    }

    private void addUniqueOptions(ArrayList<Clip> options, ArrayList<Clip> candidates, Set<Integer> seen) {
        for (Clip clip : candidates) {
            if (options.size() >= 3) return;
            if (seen.add(clip.speciesId)) {
                options.add(clip);
            }
        }
    }

    private void chooseAnswer(Button button) {
        Clip chosen = (Clip) button.getTag();
        selectedSpeciesId = chosen.speciesId;
        boolean correct = chosen.speciesId == currentClip.speciesId;
        recordAnswer(correct);
        for (Button answer : answerButtons) {
            Clip option = (Clip) answer.getTag();
            answer.setEnabled(false);
            if (option.speciesId == currentClip.speciesId) {
                answer.setTextColor(Color.WHITE);
                answer.setBackground(panelBackground(ACCENT, 0xFF));
            } else if (option.speciesId == selectedSpeciesId) {
                answer.setTextColor(Color.WHITE);
                answer.setBackground(panelBackground(RUST, 0xFF));
            }
        }
        reveal.setVisibility(View.VISIBLE);
        reveal.setText(revealText(correct, chosen));
        updateProgress();
    }

    private String revealText(boolean correct, Clip chosen) {
        String verdict = correct ? "Correct." : "Not quite. You chose " + chosen.commonName + ".";
        return verdict
                + "\n\nAnswer: " + currentClip.commonName
                + "\n" + currentClip.scientificName
                + "\nFamily: " + currentClip.family
                + "\nType: " + currentClip.clipType
                + "\nLocation: " + currentClip.location
                + "\nRecordist: " + currentClip.recordist
                + "\nLicense: " + currentClip.licenseName;
    }

    private void recordAnswer(boolean correct) {
        int attempts = prefs.getInt("attempts", 0) + 1;
        int correctCount = prefs.getInt("correct", 0) + (correct ? 1 : 0);
        prefs.edit()
                .putInt("attempts", attempts)
                .putInt("correct", correctCount)
                .apply();
    }

    private void updateProgress() {
        int attempts = prefs.getInt("attempts", 0);
        int correctCount = prefs.getInt("correct", 0);
        String accuracy = attempts == 0 ? "n/a" : String.format(Locale.US, "%d%%", Math.round((100f * correctCount) / attempts));
        progress.setText(speciesCount + " species / " + clips.size() + " clips  |  " + attempts + " attempts  |  " + accuracy + " accuracy");
    }

    private void playCurrentClip() {
        if (currentClip == null) return;
        stopAudio();
        try {
            AssetFileDescriptor descriptor = getAssets().openFd(currentClip.audio);
            player = new MediaPlayer();
            player.setDataSource(descriptor.getFileDescriptor(), descriptor.getStartOffset(), descriptor.getLength());
            descriptor.close();
            player.setOnCompletionListener(mp -> stopAudio());
            player.prepare();
            player.start();
        } catch (Exception exception) {
            Toast.makeText(this, "Could not play clip", Toast.LENGTH_SHORT).show();
        }
    }

    private void stopAudio() {
        if (player != null) {
            try {
                player.stop();
            } catch (Exception ignored) {
            }
            player.release();
            player = null;
        }
    }

    private TextView text(String value, int sp, int style, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTypeface(Typeface.DEFAULT, style);
        view.setTextColor(color);
        view.setLineSpacing(0, 1.12f);
        return view;
    }

    private Button primaryButton(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(Color.WHITE);
        button.setTextSize(15);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setAllCaps(false);
        button.setBackground(panelBackground(ACCENT, 0xFF));
        return button;
    }

    private Button secondaryButton(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(INK);
        button.setTextSize(15);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setAllCaps(false);
        button.setBackground(panelBackground(LINE, 0xFF));
        return button;
    }

    private Button answerButton() {
        Button button = secondaryButton("");
        button.setGravity(Gravity.CENTER_VERTICAL | Gravity.LEFT);
        button.setPadding(dp(16), dp(12), dp(16), dp(12));
        return button;
    }

    private LinearLayout panel() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(16), dp(16), dp(16), dp(16));
        layout.setBackground(panelBackground(PANEL, 0xFF));
        return layout;
    }

    private View spacer(int dp) {
        View view = new View(this);
        view.setLayoutParams(new LinearLayout.LayoutParams(1, dp(dp)));
        return view;
    }

    private android.graphics.drawable.GradientDrawable panelBackground(int color, int alpha) {
        android.graphics.drawable.GradientDrawable drawable = new android.graphics.drawable.GradientDrawable();
        drawable.setColor((alpha << 24) | (color & 0x00FFFFFF));
        drawable.setCornerRadius(dp(8));
        drawable.setStroke(dp(1), LINE);
        return drawable;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static class Clip {
        final int clipId;
        final int speciesId;
        final String commonName;
        final String scientificName;
        final String family;
        final String clipType;
        final String audio;
        final String location;
        final String recordist;
        final String licenseName;

        Clip(JSONObject item) throws Exception {
            clipId = item.getInt("clipId");
            speciesId = item.getInt("speciesId");
            commonName = item.getString("commonName");
            scientificName = item.getString("scientificName");
            family = item.optString("family", "Unknown");
            clipType = item.optString("clipType", "audio");
            audio = item.getString("audio");
            location = item.optString("location", "Unknown location");
            recordist = item.optString("recordist", "Unknown recordist");
            licenseName = item.optString("licenseName", "Unknown license");
        }
    }
}
