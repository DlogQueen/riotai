package com.riot.raw;

import android.app.Activity;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * RAW — social media for actual life.
 *
 * The interface is a self-contained web bundle in assets/www, rendered in a
 * WebView with no network permission. Everything the app stores stays on the
 * device, which suits a place people write down their worst weeks.
 */
public class MainActivity extends Activity {

    private WebView web;

    /**
     * The web layer's only channel back into the app.
     *
     * Static, holding the Activity explicitly, rather than an inner class: the
     * build-tools 34 d8 fails to dex non-static inner classes.
     */
    public static class Bridge implements Runnable {
        private final Activity host;

        Bridge(Activity host) {
            this.host = host;
        }

        /** Called when the web layer has no screen left to pop. */
        @JavascriptInterface
        public void exitApp() {
            host.runOnUiThread(this);
        }

        public void run() {
            host.finish();
        }
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        Window w = getWindow();
        w.setStatusBarColor(Color.BLACK);
        w.setNavigationBarColor(Color.BLACK);
        // Draw behind the system bars; the web layer handles the insets itself.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            w.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }

        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setTextZoom(100);          // Ignore system font scaling; the layout is fixed-scale.

        web.addJavascriptInterface(new Bridge(this), "RawHost");
        web.setWebViewClient(new WebViewClient());
        web.loadUrl("file:///android_asset/www/index.html");

        setContentView(web);
    }

    /**
     * Hand the hardware back button to the web layer, which pops its own screen
     * stack and calls RawHost.exitApp() once there is nothing left to pop.
     */
    @Override
    public void onBackPressed() {
        web.evaluateJavascript("window.rawBack && window.rawBack()", null);
    }
}
