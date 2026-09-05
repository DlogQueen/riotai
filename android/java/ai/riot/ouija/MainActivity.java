package ai.riot.ouija;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;

/**
 * One activity, one WebView, one board.
 *
 * The page lives in assets/ and answers from its own oracle, so the app works
 * with the radio off. Point it at a RIOT AI server under LINK and the spirits
 * start speaking through the model instead.
 */
public class MainActivity extends Activity {

    private WebView web;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);              // remembers the server you linked
        s.setMediaPlaybackRequiresUserGesture(false);   // the drone starts on its own
        s.setTextZoom(100);                        // system font scaling must not break the arcs

        web.setBackgroundColor(0xFF07060A);
        web.setKeepScreenOn(true);                 // a seance shouldn't time out
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.addJavascriptInterface(new Knocker(this), "Board");

        setContentView(web);
        goDark();
        web.loadUrl("file:///android_asset/ouija.html");
    }

    /** Fullscreen, edge to edge — the board is the whole phone. */
    private void goDark() {
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            WindowInsetsController c = getWindow().getInsetsController();
            if (c != null) {
                c.hide(WindowInsets.Type.systemBars());
                c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            web.setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        }
    }

    @Override
    public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) goDark();
    }

    /** Back doesn't wander through history — there's only one page. */
    @Override
    public void onBackPressed() {
        moveTaskToBack(true);
    }
}
