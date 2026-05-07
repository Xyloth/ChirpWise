package com.xyflow.birdtrainer;

import android.app.Activity;
import android.content.SharedPreferences;
import android.content.res.AssetFileDescriptor;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.MediaPlayer;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.Set;

public class MainActivity extends Activity {
    private enum Screen {
        LISTEN,
        QUIZ,
        STUDY,
        PROGRESS,
        SETTINGS
    }

    private static final int FOREST = Color.rgb(8, 27, 20);
    private static final int FOREST_2 = Color.rgb(12, 41, 29);
    private static final int PANEL = Color.rgb(18, 47, 33);
    private static final int PANEL_LIGHT = Color.rgb(32, 70, 44);
    private static final int CREAM = Color.rgb(246, 229, 191);
    private static final int CREAM_2 = Color.rgb(238, 214, 166);
    private static final int LEAF = Color.rgb(137, 160, 61);
    private static final int LEAF_DARK = Color.rgb(84, 111, 40);
    private static final int RUST = Color.rgb(171, 97, 58);
    private static final int LINE = Color.rgb(88, 112, 57);
    private static final int MUTED = Color.rgb(184, 195, 145);

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable playbackTicker = new Runnable() {
        @Override
        public void run() {
            updateQuizWaveformProgress();
            if (isCurrentClipPlaying()) {
                handler.postDelayed(this, 80);
            }
        }
    };
    private final Random random = new Random();
    private final ArrayList<Clip> clips = new ArrayList<>();
    private final ArrayList<Clip> speciesClips = new ArrayList<>();
    private final Map<Integer, ArrayList<Clip>> clipsBySpecies = new HashMap<>();
    private final EnumMap<Screen, TextView> navButtons = new EnumMap<>(Screen.class);
    private final ArrayList<Button> answerButtons = new ArrayList<>();

    private SharedPreferences prefs;
    private MediaPlayer player;
    private Clip activeClip;
    private LinearLayout content;
    private Screen currentScreen = Screen.LISTEN;
    private Clip currentQuizClip;
    private Clip lastPlayedClip;
    private TextView quizPrompt;
    private TextView quizReveal;
    private TextView listenNowPlaying;
    private TextView studyNowPlaying;
    private WaveformView quizWaveform;
    private Button quizPlayPauseButton;
    private int speciesCount = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window window = getWindow();
        window.setStatusBarColor(FOREST);
        window.setNavigationBarColor(FOREST);

        prefs = getSharedPreferences("chirpwise_progress", MODE_PRIVATE);
        loadDataset();
        buildIndexes();
        showSplash();
        handler.postDelayed(() -> buildShell(Screen.LISTEN), 850);
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopAudio();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopAudio();
    }

    private void loadDataset() {
        try {
            JSONObject dataset = new JSONObject(readAsset("dataset.json"));
            JSONArray items = dataset.getJSONArray("clips");
            for (int i = 0; i < items.length(); i++) {
                clips.add(new Clip(items.getJSONObject(i)));
            }
            speciesCount = dataset.optInt("speciesCount", 0);
        } catch (Exception exception) {
            throw new RuntimeException("Unable to load bundled bird dataset", exception);
        }
    }

    private void buildIndexes() {
        clipsBySpecies.clear();
        for (Clip clip : clips) {
            ArrayList<Clip> speciesList = clipsBySpecies.get(clip.speciesId);
            if (speciesList == null) {
                speciesList = new ArrayList<>();
                clipsBySpecies.put(clip.speciesId, speciesList);
            }
            speciesList.add(clip);
        }

        speciesClips.clear();
        for (ArrayList<Clip> speciesList : clipsBySpecies.values()) {
            Collections.sort(speciesList, Comparator.comparingInt(c -> c.clipId));
            speciesClips.add(speciesList.get(0));
        }
        Collections.sort(speciesClips, (a, b) -> a.commonName.compareToIgnoreCase(b.commonName));
        if (speciesCount <= 0) {
            speciesCount = speciesClips.size();
        }
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

    private void showSplash() {
        FrameLayout frame = new FrameLayout(this);
        frame.setBackground(gradient(FOREST_2, FOREST));

        LinearLayout splash = new LinearLayout(this);
        splash.setOrientation(LinearLayout.VERTICAL);
        splash.setGravity(Gravity.CENTER);
        splash.setPadding(dp(28), dp(36), dp(28), dp(36));
        frame.addView(splash, matchFrame());

        TextView region = text("Northeast birds", 15, Typeface.BOLD, LEAF);
        region.setAlpha(0.75f);
        region.setGravity(Gravity.CENTER);
        splash.addView(region);

        TextView title = text("ChirpWise", 48, Typeface.BOLD, CREAM);
        title.setTypeface(Typeface.create(Typeface.SERIF, Typeface.BOLD));
        title.setGravity(Gravity.CENTER);
        splash.addView(title);

        TextView tag = text("Hear it. Guess it. Know your birds.", 18, Typeface.BOLD, LEAF);
        tag.setGravity(Gravity.CENTER);
        splash.addView(tag);
        splash.addView(spacer(56));

        WaveformView wave = new WaveformView(this);
        wave.setSeed(42);
        wave.setColors(LEAF, Color.TRANSPARENT);
        splash.addView(wave, new LinearLayout.LayoutParams(match(), dp(64)));

        TextView loading = text("Loading calls...", 20, Typeface.BOLD, CREAM);
        loading.setGravity(Gravity.CENTER);
        splash.addView(loading);
        setContentView(frame);
    }

    private void buildShell(Screen screen) {
        LinearLayout shell = new LinearLayout(this);
        shell.setOrientation(LinearLayout.VERTICAL);
        shell.setBackground(gradient(FOREST_2, FOREST));

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(false);
        scroll.setOverScrollMode(View.OVER_SCROLL_NEVER);

        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(18), dp(18), dp(18), dp(18));
        scroll.addView(content, new ScrollView.LayoutParams(match(), wrap()));
        shell.addView(scroll, new LinearLayout.LayoutParams(match(), 0, 1f));

        shell.addView(buildNav(), new LinearLayout.LayoutParams(match(), dp(86)));
        setContentView(shell);
        showScreen(screen);
    }

    private LinearLayout buildNav() {
        navButtons.clear();
        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setGravity(Gravity.CENTER);
        nav.setPadding(dp(8), dp(8), dp(8), dp(10));
        nav.setBackground(round(PANEL, FOREST, 0, 0xFF));
        addNavButton(nav, Screen.LISTEN, "Listen");
        addNavButton(nav, Screen.QUIZ, "Quiz");
        addNavButton(nav, Screen.STUDY, "Study");
        addNavButton(nav, Screen.PROGRESS, "Progress");
        addNavButton(nav, Screen.SETTINGS, "Settings");
        return nav;
    }

    private void addNavButton(LinearLayout nav, Screen screen, String label) {
        TextView button = text(label, 12, Typeface.BOLD, CREAM);
        button.setGravity(Gravity.CENTER);
        button.setMinHeight(dp(54));
        button.setOnClickListener(view -> showScreen(screen));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(62), 1f);
        params.setMargins(dp(3), 0, dp(3), 0);
        nav.addView(button, params);
        navButtons.put(screen, button);
    }

    private void showScreen(Screen screen) {
        currentScreen = screen;
        stopAudio();
        content.removeAllViews();
        addBrandHeader();

        if (screen == Screen.LISTEN) {
            buildListenScreen();
        } else if (screen == Screen.QUIZ) {
            buildQuizScreen();
        } else if (screen == Screen.STUDY) {
            buildStudyScreen();
        } else if (screen == Screen.PROGRESS) {
            buildProgressScreen();
        } else {
            buildSettingsScreen();
        }
        refreshNav();
    }

    private void refreshNav() {
        for (Map.Entry<Screen, TextView> entry : navButtons.entrySet()) {
            boolean selected = entry.getKey() == currentScreen;
            TextView button = entry.getValue();
            button.setTextColor(selected ? FOREST : CREAM);
            button.setBackground(round(selected ? CREAM : PANEL_LIGHT, selected ? CREAM : LINE, 18, 0xFF));
            button.setAlpha(selected ? 1f : 0.9f);
        }
    }

    private void addBrandHeader() {
        LinearLayout hero = panel(20, true);
        hero.setGravity(Gravity.CENTER_HORIZONTAL);
        hero.setPadding(dp(18), dp(18), dp(18), dp(18));

        TextView title = text("ChirpWise", 38, Typeface.BOLD, CREAM);
        title.setTypeface(Typeface.create(Typeface.SERIF, Typeface.BOLD));
        title.setGravity(Gravity.CENTER);
        hero.addView(title);

        TextView tag = text("Hear it. Guess it. Know your birds.", 15, Typeface.BOLD, LEAF);
        tag.setGravity(Gravity.CENTER);
        hero.addView(tag);

        TextView region = chip("Northeast / Ohio Valley");
        region.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams regionParams = new LinearLayout.LayoutParams(wrap(), dp(34));
        regionParams.setMargins(0, dp(14), 0, 0);
        hero.addView(region, regionParams);

        content.addView(hero, fullWidth());
        content.addView(spacer(14));
    }

    private void buildListenScreen() {
        LinearLayout actions = panel(20, false);
        actions.addView(sectionTitle("Listen fast"));
        actions.addView(body("Search a bird, tap it, and the sound starts. No quiz, no extra steps."));
        actions.addView(spacer(12));

        Button randomListen = primaryButton("Listen to a random bird");
        randomListen.setOnClickListener(view -> {
            Clip clip = pickRandomClip();
            listenNowPlaying.setText(nowPlayingText(clip));
            playClip(clip);
        });
        actions.addView(randomListen, fullButton());
        actions.addView(spacer(10));

        Button startQuiz = creamButton("Start Quiz");
        startQuiz.setOnClickListener(view -> showScreen(Screen.QUIZ));
        actions.addView(startQuiz, fullButton());
        actions.addView(spacer(10));

        Button study = secondaryButton("Study bird sounds");
        study.setOnClickListener(view -> showScreen(Screen.STUDY));
        actions.addView(study, fullButton());
        actions.addView(spacer(12));

        listenNowPlaying = body(lastPlayedClip == null ? "Nothing playing yet." : nowPlayingText(lastPlayedClip));
        listenNowPlaying.setTextColor(CREAM_2);
        actions.addView(listenNowPlaying);
        content.addView(actions, fullWidth());
        content.addView(spacer(14));

        addSearchBlock(content, "Quick sound finder", 10, clip -> {
            lastPlayedClip = clip;
            listenNowPlaying.setText(nowPlayingText(clip));
            playClip(clip);
        });
    }

    private void buildQuizScreen() {
        answerButtons.clear();
        LinearLayout card = panel(20, false);
        card.addView(sectionTitle("Identify by sound"));
        card.addView(body("Play the hidden clip, choose the bird, then see the source and location."));
        card.addView(spacer(12));

        quizWaveform = new WaveformView(this);
        quizWaveform.setColors(LEAF, Color.argb(55, 137, 160, 61));
        card.addView(quizWaveform, new LinearLayout.LayoutParams(match(), dp(74)));

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setGravity(Gravity.CENTER);

        Button back = secondaryButton("-5s");
        back.setOnClickListener(view -> seekQuizBy(-5000));
        controls.addView(back, new LinearLayout.LayoutParams(0, dp(58), 0.72f));

        quizPlayPauseButton = primaryButton("Play");
        quizPlayPauseButton.setOnClickListener(view -> toggleQuizPlayback());
        LinearLayout.LayoutParams playParams = new LinearLayout.LayoutParams(0, dp(58), 1.35f);
        playParams.setMargins(dp(8), 0, dp(8), 0);
        controls.addView(quizPlayPauseButton, playParams);

        Button forward = secondaryButton("+5s");
        forward.setOnClickListener(view -> seekQuizBy(5000));
        controls.addView(forward, new LinearLayout.LayoutParams(0, dp(58), 0.72f));

        card.addView(controls, fullWidth());
        card.addView(spacer(10));

        quizPrompt = text("Which bird is this?", 20, Typeface.BOLD, CREAM);
        card.addView(quizPrompt);
        quizReveal = body("");
        quizReveal.setVisibility(View.GONE);
        card.addView(spacer(10));
        card.addView(quizReveal);

        content.addView(card, fullWidth());
        content.addView(spacer(12));

        for (int i = 0; i < 3; i++) {
            Button answer = answerButton();
            final Button chosen = answer;
            answer.setOnClickListener(view -> chooseAnswer(chosen));
            answerButtons.add(answer);
            content.addView(answer, fullButton());
            content.addView(spacer(10));
        }

        Button next = secondaryButton("Next bird");
        next.setOnClickListener(view -> nextQuestion());
        content.addView(next, fullButton());
        nextQuestion();
    }

    private void buildStudyScreen() {
        LinearLayout intro = panel(20, false);
        intro.addView(sectionTitle("Study library"));
        intro.addView(body("Alphabetical bird sounds. Tap any result to play immediately."));
        intro.addView(spacer(12));
        studyNowPlaying = body(lastPlayedClip == null ? "Pick a bird to hear its call." : nowPlayingText(lastPlayedClip));
        studyNowPlaying.setTextColor(CREAM_2);
        intro.addView(studyNowPlaying);
        content.addView(intro, fullWidth());
        content.addView(spacer(14));

        addSearchBlock(content, "Find a bird", 40, clip -> {
            lastPlayedClip = clip;
            studyNowPlaying.setText(nowPlayingText(clip));
            playClip(clip);
        });
    }

    private void buildProgressScreen() {
        ProgressCounts counts = computeProgressCounts();

        LinearLayout card = panel(20, false);
        card.addView(sectionTitle("Your bird map"));
        card.addView(body("Green is solid, gold is learning, rust needs another listen, and the dark arc is still unseen."));
        card.addView(spacer(12));

        ProgressRingView ring = new ProgressRingView(this);
        ring.setCounts(counts.known, counts.learning, counts.needsPractice, counts.unseen);
        card.addView(ring, new LinearLayout.LayoutParams(match(), dp(190)));

        card.addView(spacer(8));
        card.addView(bigStat(counts.known + " known", "Birds you have answered correctly more than once."));
        card.addView(spacer(8));
        card.addView(bigStat(counts.needsPractice + " need practice", "Birds that have tripped you up."));
        card.addView(spacer(8));
        card.addView(bigStat(counts.unseen + " unseen", "Birds still waiting in the pack."));
        content.addView(card, fullWidth());

        content.addView(spacer(14));
        LinearLayout summary = panel(20, false);
        summary.addView(sectionTitle("Session rhythm"));
        summary.addView(body(progressSummaryText()));
        summary.addView(spacer(10));
        summary.addView(progressBar(counts.known + counts.learning, speciesCount, LEAF));
        content.addView(summary, fullWidth());

        content.addView(spacer(14));
        addBirdList("Needs another listen", birdsNeedingPractice(), 8);
        content.addView(spacer(14));
        addBirdList("Recently heard", recentBirds(), 8);
    }

    private void buildSettingsScreen() {
        LinearLayout card = panel(20, false);
        card.addView(sectionTitle("Settings"));
        card.addView(body("ChirpWise is using the offline Northeast / Ohio Valley pack."));
        card.addView(spacer(12));
        card.addView(bigStat(speciesCount + " species", "Regional birds with real Xeno-canto recordings."));
        card.addView(spacer(8));
        card.addView(bigStat(clips.size() + " clips", "20-second practice sounds bundled in the app."));
        card.addView(spacer(14));

        Button reset = creamButton("Reset progress");
        reset.setOnClickListener(view -> {
            prefs.edit().clear().apply();
            buildSettingsScreenAfterReset();
        });
        card.addView(reset, fullButton());
        card.addView(spacer(12));
        card.addView(body("Every answer stores only local progress on this phone."));
        content.addView(card, fullWidth());
    }

    private void buildSettingsScreenAfterReset() {
        showScreen(Screen.SETTINGS);
    }

    private void addSearchBlock(LinearLayout parent, String title, int limit, ClipAction action) {
        LinearLayout card = panel(20, false);
        card.addView(sectionTitle(title));

        EditText search = new EditText(this);
        search.setSingleLine(true);
        search.setTextColor(CREAM);
        search.setHintTextColor(MUTED);
        search.setTextSize(16);
        search.setHint("Search Northern Cardinal");
        search.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_WORDS);
        search.setPadding(dp(16), 0, dp(16), 0);
        search.setBackground(round(Color.rgb(11, 34, 24), LINE, 18, 0xFF));
        card.addView(search, new LinearLayout.LayoutParams(match(), dp(54)));
        card.addView(spacer(12));

        LinearLayout results = new LinearLayout(this);
        results.setOrientation(LinearLayout.VERTICAL);
        card.addView(results);
        parent.addView(card, fullWidth());

        Runnable refresh = () -> fillBirdResults(results, search.getText().toString(), limit, action);
        search.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
                refresh.run();
            }

            @Override
            public void afterTextChanged(Editable s) {
            }
        });
        refresh.run();
    }

    private void fillBirdResults(LinearLayout results, String query, int limit, ClipAction action) {
        results.removeAllViews();
        String needle = query.trim().toLowerCase(Locale.US);
        int shown = 0;
        for (Clip clip : speciesClips) {
            if (!needle.isEmpty()
                    && !clip.commonName.toLowerCase(Locale.US).contains(needle)
                    && !clip.scientificName.toLowerCase(Locale.US).contains(needle)) {
                continue;
            }
            results.addView(birdRow(clip, action), fullWidth());
            shown++;
            if (shown >= limit) {
                break;
            }
        }
        if (shown == 0) {
            TextView empty = body("No match yet. Try a common name or Latin name.");
            results.addView(empty);
        }
    }

    private LinearLayout birdRow(Clip clip, ClipAction action) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(10), dp(12), dp(10));
        row.setBackground(round(PANEL_LIGHT, LINE, 18, 0xFF));
        row.setOnClickListener(view -> action.run(clip));

        LinearLayout names = new LinearLayout(this);
        names.setOrientation(LinearLayout.VERTICAL);
        TextView common = text(clip.commonName, 16, Typeface.BOLD, CREAM);
        TextView scientific = text(clip.scientificName, 12, Typeface.NORMAL, MUTED);
        names.addView(common);
        names.addView(scientific);
        row.addView(names, new LinearLayout.LayoutParams(0, wrap(), 1f));

        TextView play = chip("Play");
        play.setGravity(Gravity.CENTER);
        row.addView(play, new LinearLayout.LayoutParams(dp(66), dp(36)));

        LinearLayout.LayoutParams rowMargin = new LinearLayout.LayoutParams(match(), wrap());
        rowMargin.setMargins(0, 0, 0, dp(9));
        row.setLayoutParams(rowMargin);
        return row;
    }

    private void addBirdList(String title, ArrayList<Clip> birds, int limit) {
        LinearLayout card = panel(20, false);
        card.addView(sectionTitle(title));
        if (birds.isEmpty()) {
            card.addView(body("Nothing here yet. Play a few quiz rounds and this fills in."));
        } else {
            int shown = 0;
            for (Clip clip : birds) {
                card.addView(birdRow(clip, c -> {
                    lastPlayedClip = c;
                    playClip(c);
                }), fullWidth());
                shown++;
                if (shown >= limit) {
                    break;
                }
            }
        }
        content.addView(card, fullWidth());
    }

    private void nextQuestion() {
        stopAudio();
        currentQuizClip = pickQuizClip();
        quizWaveform.setSeed(currentQuizClip.clipId);
        quizWaveform.setPeaks(currentQuizClip.waveform);
        quizWaveform.setProgress(0f);
        updateQuizPlayPauseButton();
        quizReveal.setVisibility(View.GONE);
        quizPrompt.setText("Which bird is this?");

        ArrayList<Clip> options = buildOptions(currentQuizClip);
        for (int i = 0; i < answerButtons.size(); i++) {
            Clip option = options.get(i);
            Button button = answerButtons.get(i);
            button.setTag(option);
            button.setText(choiceLabel(i, option));
            button.setEnabled(true);
            button.setAlpha(1f);
            button.setTextColor(CREAM);
            button.setBackground(round(PANEL_LIGHT, LINE, 18, 0xFF));
        }
    }

    private Clip pickQuizClip() {
        ArrayList<Clip> needs = new ArrayList<>();
        ArrayList<Clip> unseen = new ArrayList<>();
        for (Clip clip : speciesClips) {
            int attempts = speciesAttempts(clip.speciesId);
            int correct = speciesCorrect(clip.speciesId);
            int wrong = speciesWrong(clip.speciesId);
            if (attempts == 0) {
                unseen.add(randomClipForSpecies(clip.speciesId));
            } else if (wrong >= correct && wrong > 0) {
                needs.add(randomClipForSpecies(clip.speciesId));
            }
        }
        int roll = random.nextInt(100);
        if (!needs.isEmpty() && roll < 45) {
            return needs.get(random.nextInt(needs.size()));
        }
        if (!unseen.isEmpty() && roll < 80) {
            return unseen.get(random.nextInt(unseen.size()));
        }
        return pickRandomClip();
    }

    private Clip pickRandomClip() {
        if (clips.isEmpty()) {
            throw new IllegalStateException("No clips bundled");
        }
        return clips.get(random.nextInt(clips.size()));
    }

    private Clip randomClipForSpecies(int speciesId) {
        ArrayList<Clip> speciesList = clipsBySpecies.get(speciesId);
        if (speciesList == null || speciesList.isEmpty()) {
            return pickRandomClip();
        }
        return speciesList.get(random.nextInt(speciesList.size()));
    }

    private ArrayList<Clip> buildOptions(Clip answer) {
        ArrayList<Clip> sameFamily = new ArrayList<>();
        ArrayList<Clip> others = new ArrayList<>();
        Set<Integer> seen = new HashSet<>();
        seen.add(answer.speciesId);

        for (Clip clip : speciesClips) {
            if (clip.speciesId == answer.speciesId) {
                continue;
            }
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
        Collections.shuffle(options, random);
        return options;
    }

    private void addUniqueOptions(ArrayList<Clip> options, ArrayList<Clip> candidates, Set<Integer> seen) {
        for (Clip clip : candidates) {
            if (options.size() >= 3) {
                return;
            }
            if (seen.add(clip.speciesId)) {
                options.add(clip);
            }
        }
    }

    private void chooseAnswer(Button button) {
        Clip chosen = (Clip) button.getTag();
        boolean correct = chosen.speciesId == currentQuizClip.speciesId;
        recordAnswer(currentQuizClip, correct);

        for (Button answer : answerButtons) {
            Clip option = (Clip) answer.getTag();
            answer.setEnabled(false);
            if (option.speciesId == currentQuizClip.speciesId) {
                answer.setTextColor(FOREST);
                answer.setBackground(round(CREAM, CREAM_2, 18, 0xFF));
            } else if (option.speciesId == chosen.speciesId) {
                answer.setTextColor(CREAM);
                answer.setBackground(round(RUST, RUST, 18, 0xFF));
            } else {
                answer.setAlpha(0.62f);
            }
        }

        quizReveal.setVisibility(View.VISIBLE);
        quizReveal.setText(revealText(correct, chosen));
    }

    private void recordAnswer(Clip clip, boolean correct) {
        int attempts = prefs.getInt("attempts", 0) + 1;
        int correctCount = prefs.getInt("correct", 0) + (correct ? 1 : 0);
        int speciesAttempts = speciesAttempts(clip.speciesId) + 1;
        int speciesCorrect = speciesCorrect(clip.speciesId) + (correct ? 1 : 0);
        int speciesWrong = speciesWrong(clip.speciesId) + (correct ? 0 : 1);

        SharedPreferences.Editor editor = prefs.edit()
                .putInt("attempts", attempts)
                .putInt("correct", correctCount)
                .putInt("species_attempts_" + clip.speciesId, speciesAttempts)
                .putInt("species_correct_" + clip.speciesId, speciesCorrect)
                .putInt("species_wrong_" + clip.speciesId, speciesWrong);
        updateStreak(editor);
        updateRecent(editor, clip.speciesId);
        editor.apply();
    }

    private void updateStreak(SharedPreferences.Editor editor) {
        long today = System.currentTimeMillis() / 86400000L;
        long lastDay = prefs.getLong("last_day", -1L);
        int streak = prefs.getInt("streak", 0);
        if (lastDay == today) {
            return;
        }
        if (lastDay == today - 1L) {
            streak += 1;
        } else {
            streak = 1;
        }
        editor.putLong("last_day", today).putInt("streak", streak);
    }

    private void updateRecent(SharedPreferences.Editor editor, int speciesId) {
        String current = prefs.getString("recent_species", "");
        ArrayList<String> ids = new ArrayList<>();
        ids.add(String.valueOf(speciesId));
        for (String value : current.split(",")) {
            if (value.trim().isEmpty() || value.equals(String.valueOf(speciesId))) {
                continue;
            }
            ids.add(value);
            if (ids.size() >= 12) {
                break;
            }
        }
        editor.putString("recent_species", join(ids));
    }

    private String join(ArrayList<String> ids) {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < ids.size(); i++) {
            if (i > 0) {
                builder.append(",");
            }
            builder.append(ids.get(i));
        }
        return builder.toString();
    }

    private String revealText(boolean correct, Clip chosen) {
        String first = correct ? "Correct. That's " + currentQuizClip.commonName + "."
                : "Not quite. That was " + currentQuizClip.commonName + ".";
        return first
                + "\n\nYou chose: " + chosen.commonName
                + "\nSound: " + cleanSoundType(currentQuizClip.clipType)
                + "\nPlace: " + currentQuizClip.location
                + "\nRecordist: " + currentQuizClip.recordist
                + "\nLicense: " + currentQuizClip.licenseName;
    }

    private void playHiddenQuizClip() {
        playClip(currentQuizClip);
    }

    private void playClip(Clip clip) {
        if (clip == null) {
            return;
        }
        stopAudio();
        lastPlayedClip = clip;
        try {
            AssetFileDescriptor descriptor = getAssets().openFd(clip.audio);
            player = new MediaPlayer();
            activeClip = clip;
            player.setDataSource(descriptor.getFileDescriptor(), descriptor.getStartOffset(), descriptor.getLength());
            descriptor.close();
            player.setOnCompletionListener(mp -> {
                Clip finished = activeClip;
                stopAudio();
                if (finished == currentQuizClip && quizWaveform != null) {
                    quizWaveform.setProgress(1f);
                }
            });
            player.prepare();
            player.start();
            startPlaybackTicker();
            updateQuizPlayPauseButton();
        } catch (Exception exception) {
            stopAudio();
            showPlaybackError();
        }
    }

    private void toggleQuizPlayback() {
        if (currentQuizClip == null) {
            return;
        }
        if (player != null && activeClip == currentQuizClip) {
            try {
                if (player.isPlaying()) {
                    player.pause();
                    updateQuizWaveformProgress();
                    updateQuizPlayPauseButton();
                    return;
                }
                player.start();
                startPlaybackTicker();
                updateQuizPlayPauseButton();
                return;
            } catch (IllegalStateException ignored) {
                stopAudio();
            }
        }
        playHiddenQuizClip();
    }

    private void seekQuizBy(int deltaMillis) {
        if (currentQuizClip == null) {
            return;
        }
        if (player == null || activeClip != currentQuizClip) {
            playHiddenQuizClip();
        }
        if (player == null) {
            return;
        }
        try {
            int duration = Math.max(1, player.getDuration());
            int target = player.getCurrentPosition() + deltaMillis;
            target = Math.max(0, Math.min(duration - 250, target));
            player.seekTo(target);
            updateQuizWaveformProgress();
            startPlaybackTicker();
            updateQuizPlayPauseButton();
        } catch (IllegalStateException ignored) {
            stopAudio();
        }
    }

    private void stopAudio() {
        handler.removeCallbacks(playbackTicker);
        if (player != null) {
            try {
                player.stop();
            } catch (Exception ignored) {
            }
            player.release();
            player = null;
        }
        activeClip = null;
        updateQuizPlayPauseButton();
    }

    private void startPlaybackTicker() {
        handler.removeCallbacks(playbackTicker);
        updateQuizWaveformProgress();
        handler.postDelayed(playbackTicker, 80);
    }

    private void updateQuizWaveformProgress() {
        if (quizWaveform == null || player == null || activeClip != currentQuizClip) {
            return;
        }
        try {
            int duration = Math.max(1, player.getDuration());
            quizWaveform.setProgress(Math.max(0f, Math.min(1f, player.getCurrentPosition() / (float) duration)));
        } catch (IllegalStateException ignored) {
        }
    }

    private boolean isCurrentClipPlaying() {
        if (player == null || activeClip != currentQuizClip) {
            return false;
        }
        try {
            return player.isPlaying();
        } catch (IllegalStateException exception) {
            return false;
        }
    }

    private void updateQuizPlayPauseButton() {
        if (quizPlayPauseButton != null) {
            quizPlayPauseButton.setText(isCurrentClipPlaying() ? "Pause" : "Play");
        }
    }

    private void showPlaybackError() {
        if (currentScreen == Screen.LISTEN && listenNowPlaying != null) {
            listenNowPlaying.setText("Could not play this clip.");
        } else if (currentScreen == Screen.STUDY && studyNowPlaying != null) {
            studyNowPlaying.setText("Could not play this clip.");
        } else if (currentScreen == Screen.QUIZ && quizPrompt != null) {
            quizPrompt.setText("Could not play this clip.");
        }
    }

    private ProgressCounts computeProgressCounts() {
        ProgressCounts counts = new ProgressCounts();
        for (Clip clip : speciesClips) {
            int attempts = speciesAttempts(clip.speciesId);
            int correct = speciesCorrect(clip.speciesId);
            int wrong = speciesWrong(clip.speciesId);
            if (attempts == 0) {
                counts.unseen++;
            } else if (correct >= 2 && correct >= wrong) {
                counts.known++;
            } else if (wrong > correct) {
                counts.needsPractice++;
            } else {
                counts.learning++;
            }
        }
        return counts;
    }

    private ArrayList<Clip> birdsNeedingPractice() {
        ArrayList<Clip> birds = new ArrayList<>();
        for (Clip clip : speciesClips) {
            if (speciesWrong(clip.speciesId) > speciesCorrect(clip.speciesId)) {
                birds.add(clip);
            }
        }
        Collections.sort(birds, (a, b) -> Integer.compare(speciesWrong(b.speciesId), speciesWrong(a.speciesId)));
        return birds;
    }

    private ArrayList<Clip> recentBirds() {
        ArrayList<Clip> birds = new ArrayList<>();
        String recent = prefs.getString("recent_species", "");
        for (String value : recent.split(",")) {
            if (value.trim().isEmpty()) {
                continue;
            }
            Clip clip = findSpeciesClip(parseInt(value));
            if (clip != null) {
                birds.add(clip);
            }
        }
        return birds;
    }

    private Clip findSpeciesClip(int speciesId) {
        for (Clip clip : speciesClips) {
            if (clip.speciesId == speciesId) {
                return clip;
            }
        }
        return null;
    }

    private int speciesAttempts(int speciesId) {
        return prefs.getInt("species_attempts_" + speciesId, 0);
    }

    private int speciesCorrect(int speciesId) {
        return prefs.getInt("species_correct_" + speciesId, 0);
    }

    private int speciesWrong(int speciesId) {
        return prefs.getInt("species_wrong_" + speciesId, 0);
    }

    private String progressSummaryText() {
        int attempts = prefs.getInt("attempts", 0);
        int correct = prefs.getInt("correct", 0);
        int streak = prefs.getInt("streak", 0);
        if (attempts == 0) {
            return "No quiz answers yet. Start a round and ChirpWise will track what sticks.";
        }
        int accuracy = Math.round((100f * correct) / attempts);
        return streak + " day streak. " + correct + " right out of " + attempts + ". " + accuracy + "% accuracy.";
    }

    private LinearLayout bigStat(String value, String label) {
        LinearLayout stat = new LinearLayout(this);
        stat.setOrientation(LinearLayout.VERTICAL);
        stat.setPadding(dp(14), dp(10), dp(14), dp(10));
        stat.setBackground(round(Color.rgb(12, 36, 25), LINE, 16, 0xFF));
        TextView main = text(value, 20, Typeface.BOLD, CREAM);
        TextView sub = text(label, 13, Typeface.NORMAL, MUTED);
        stat.addView(main);
        stat.addView(sub);
        return stat;
    }

    private View progressBar(int value, int total, int color) {
        LinearLayout wrap = new LinearLayout(this);
        wrap.setOrientation(LinearLayout.HORIZONTAL);
        wrap.setPadding(0, 0, 0, 0);
        wrap.setBackground(round(Color.rgb(8, 26, 18), LINE, 12, 0xFF));
        int safeTotal = Math.max(total, 1);
        int width = value <= 0 ? 0 : Math.max(1, Math.round(1000f * value / safeTotal));

        View fill = new View(this);
        fill.setBackground(round(color, color, 12, 0xFF));
        wrap.addView(fill, new LinearLayout.LayoutParams(0, dp(18), width));
        View rest = new View(this);
        wrap.addView(rest, new LinearLayout.LayoutParams(0, dp(18), 1000 - width));
        return wrap;
    }

    private String nowPlayingText(Clip clip) {
        return "Now playing: " + clip.commonName
                + "\n" + cleanSoundType(clip.clipType)
                + "\n" + clip.location;
    }

    private String choiceLabel(int index, Clip option) {
        char letter = (char) ('A' + index);
        return letter + "   " + option.commonName + "\n" + option.scientificName;
    }

    private String cleanSoundType(String value) {
        if (value == null || value.trim().isEmpty()) {
            return "bird sound";
        }
        return value.replace(";", ", ");
    }

    private int parseInt(String value) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException exception) {
            return -1;
        }
    }

    private TextView sectionTitle(String value) {
        return text(value, 22, Typeface.BOLD, CREAM);
    }

    private TextView body(String value) {
        TextView text = text(value, 14, Typeface.NORMAL, MUTED);
        text.setLineSpacing(0, 1.18f);
        return text;
    }

    private TextView chip(String value) {
        TextView chip = text(value, 13, Typeface.BOLD, CREAM);
        chip.setPadding(dp(12), 0, dp(12), 0);
        chip.setBackground(round(Color.rgb(42, 71, 34), LINE, 16, 0xFF));
        return chip;
    }

    private TextView text(String value, int sp, int style, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTypeface(Typeface.DEFAULT, style);
        view.setTextColor(color);
        view.setIncludeFontPadding(true);
        return view;
    }

    private Button primaryButton(String label) {
        return styledButton(label, LEAF_DARK, LINE, CREAM);
    }

    private Button creamButton(String label) {
        return styledButton(label, CREAM, CREAM_2, FOREST);
    }

    private Button secondaryButton(String label) {
        return styledButton(label, PANEL_LIGHT, LINE, CREAM);
    }

    private Button answerButton() {
        Button button = styledButton("", PANEL_LIGHT, LINE, CREAM);
        button.setGravity(Gravity.CENTER_VERTICAL | Gravity.LEFT);
        button.setTextSize(15);
        button.setMinHeight(dp(66));
        return button;
    }

    private Button styledButton(String label, int fill, int stroke, int textColor) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(textColor);
        button.setTextSize(16);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setAllCaps(false);
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(16), 0, dp(16), 0);
        button.setMinHeight(dp(56));
        button.setBackground(round(fill, stroke, 18, 0xFF));
        button.setElevation(dp(3));
        return button;
    }

    private LinearLayout panel(int radius, boolean hero) {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(16), dp(16), dp(16), dp(16));
        layout.setBackground(round(hero ? Color.rgb(13, 40, 27) : PANEL, LINE, radius, 0xF4));
        layout.setElevation(dp(2));
        return layout;
    }

    private GradientDrawable round(int fill, int stroke, int radius, int alpha) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor((alpha << 24) | (fill & 0x00FFFFFF));
        drawable.setCornerRadius(dp(radius));
        drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    private GradientDrawable gradient(int top, int bottom) {
        GradientDrawable drawable = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, new int[]{top, bottom});
        drawable.setDither(true);
        return drawable;
    }

    private LinearLayout.LayoutParams fullWidth() {
        return new LinearLayout.LayoutParams(match(), wrap());
    }

    private LinearLayout.LayoutParams fullButton() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(match(), dp(58));
        params.setMargins(0, 0, 0, 0);
        return params;
    }

    private FrameLayout.LayoutParams matchFrame() {
        return new FrameLayout.LayoutParams(match(), match());
    }

    private View spacer(int dp) {
        View view = new View(this);
        view.setLayoutParams(new LinearLayout.LayoutParams(1, dp(dp)));
        return view;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private int match() {
        return ViewGroup.LayoutParams.MATCH_PARENT;
    }

    private int wrap() {
        return ViewGroup.LayoutParams.WRAP_CONTENT;
    }

    private interface ClipAction {
        void run(Clip clip);
    }

    private static class ProgressCounts {
        int known;
        int learning;
        int needsPractice;
        int unseen;
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
        final float[] waveform;

        Clip(JSONObject item) throws Exception {
            clipId = item.getInt("clipId");
            speciesId = item.getInt("speciesId");
            commonName = item.getString("commonName");
            scientificName = item.getString("scientificName");
            family = item.optString("family", "Unknown");
            clipType = item.optString("clipType", "bird sound");
            audio = item.getString("audio");
            location = item.optString("location", "Unknown location");
            recordist = item.optString("recordist", "Unknown recordist");
            licenseName = item.optString("licenseName", "Unknown license");
            JSONArray waveformItems = item.optJSONArray("waveform");
            if (waveformItems == null || waveformItems.length() == 0) {
                waveform = new float[0];
            } else {
                waveform = new float[waveformItems.length()];
                for (int i = 0; i < waveformItems.length(); i++) {
                    waveform[i] = (float) waveformItems.optDouble(i, 0.0);
                }
            }
        }
    }

    public static class WaveformView extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private int seed = 7;
        private int barColor = LEAF;
        private int fillColor = Color.TRANSPARENT;
        private float progress = 0f;
        private float[] peaks = new float[0];

        public WaveformView(android.content.Context context) {
            super(context);
        }

        public void setSeed(int seed) {
            this.seed = seed;
            invalidate();
        }

        public void setPeaks(float[] peaks) {
            this.peaks = peaks == null ? new float[0] : peaks;
            invalidate();
        }

        public void setProgress(float progress) {
            this.progress = Math.max(0f, Math.min(1f, progress));
            invalidate();
        }

        public void setColors(int barColor, int fillColor) {
            this.barColor = barColor;
            this.fillColor = fillColor;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            int width = getWidth();
            int height = getHeight();
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(fillColor);
            canvas.drawRoundRect(0, 0, width, height, height / 3f, height / 3f, paint);

            paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setStrokeWidth(Math.max(4f, width / 90f));
            int bars = peaks.length > 0 ? peaks.length : 28;
            float gap = width / (float) (bars + 2);
            float center = height / 2f;
            for (int i = 0; i < bars; i++) {
                float wave = peaks.length > 0 ? peaks[i] : generatedWave(i);
                float half = Math.min(height * 0.42f, height * Math.max(0.12f, wave) * 0.42f);
                float x = gap * (i + 1.5f);
                paint.setColor(barColorForIndex(i, bars));
                canvas.drawLine(x, center - half, x, center + half, paint);
            }
        }

        private float generatedWave(int index) {
            int mixed = Math.abs((seed + 31) * (index + 9) * 1103515245);
            float wave = 0.28f + (mixed % 100) / 145f;
            if (index % 7 == 0) {
                wave *= 1.25f;
            }
            return wave;
        }

        private int barColorForIndex(int index, int bars) {
            if (progress <= 0f) {
                return barColor;
            }
            float playedBars = progress * bars;
            if (index <= playedBars) {
                return CREAM;
            }
            return Color.argb(110, Color.red(barColor), Color.green(barColor), Color.blue(barColor));
        }
    }

    public static class ProgressRingView extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF arc = new RectF();
        private int known;
        private int learning;
        private int needsPractice;
        private int unseen;

        public ProgressRingView(android.content.Context context) {
            super(context);
        }

        public void setCounts(int known, int learning, int needsPractice, int unseen) {
            this.known = known;
            this.learning = learning;
            this.needsPractice = needsPractice;
            this.unseen = unseen;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            int width = getWidth();
            int height = getHeight();
            int size = Math.min(width, height) - 28;
            float left = (width - size) / 2f;
            float top = (height - size) / 2f;
            arc.set(left, top, left + size, top + size);

            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setStrokeWidth(Math.max(16f, size / 12f));

            int total = Math.max(1, known + learning + needsPractice + unseen);
            float start = -90f;
            start = drawPart(canvas, start, known, total, LEAF);
            start = drawPart(canvas, start, learning, total, CREAM_2);
            start = drawPart(canvas, start, needsPractice, total, RUST);
            drawPart(canvas, start, unseen, total, Color.rgb(35, 61, 43));

            paint.setStyle(Paint.Style.FILL);
            paint.setColor(CREAM);
            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
            paint.setTextSize(size / 6.3f);
            canvas.drawText(String.valueOf(known + learning), width / 2f, height / 2f, paint);
            paint.setTextSize(size / 13f);
            paint.setColor(MUTED);
            canvas.drawText("birds heard", width / 2f, height / 2f + size / 7f, paint);
        }

        private float drawPart(Canvas canvas, float start, int count, int total, int color) {
            if (count <= 0) {
                return start;
            }
            float sweep = Math.max(3f, 360f * count / total);
            paint.setColor(color);
            canvas.drawArc(arc, start, sweep - 3f, false, paint);
            return start + sweep;
        }
    }
}
