package com.intheraw.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * In the Raw — social media for actual life.
 *
 * The interface is a self-contained web bundle in assets/www, rendered in a
 * WebView with no network permission. Everything the app stores — including
 * every photo — stays on the device, which suits a place people write down
 * their worst weeks.
 */
public class MainActivity extends Activity {

    private static final int PICK_IMAGE = 1001;

    private WebView web;

    /** Held between launching the picker and the result coming back. */
    private ValueCallback<Uri[]> pendingPick;

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
        s.setAllowContentAccess(true);   // needed to read the content:// a picker returns
        s.setTextZoom(100);              // ignore system font scaling; the layout is fixed-scale

        // Lets <input type="file"> in the web layer open the system photo picker.
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view,
                                             ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (pendingPick != null) {
                    pendingPick.onReceiveValue(null);
                }
                pendingPick = callback;
                try {
                    startActivityForResult(params.createIntent(), PICK_IMAGE);
                    return true;
                } catch (Exception e) {
                    pendingPick = null;
                    return false;
                }
            }
        });

        web.setWebViewClient(new WebViewClient());
        web.loadUrl("file:///android_asset/www/index.html");

        setContentView(web);
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        if (request != PICK_IMAGE) {
            super.onActivityResult(request, result, data);
            return;
        }
        if (pendingPick == null) {
            return;
        }
        // A cancelled pick must still resolve the callback, or the file input
        // stays wedged and the user cannot try again.
        Uri[] picked = null;
        if (result == RESULT_OK && data != null && data.getData() != null) {
            picked = new Uri[] { data.getData() };
        }
        pendingPick.onReceiveValue(picked);
        pendingPick = null;
    }

    /** Hand the hardware back button to the web layer before falling through. */
    @Override
    public void onBackPressed() {
        web.evaluateJavascript("window.rawBack && window.rawBack()", new ValueCallback<String>() {
            @Override
            public void onReceiveValue(String handled) {
                if (!"true".equals(handled)) {
                    MainActivity.super.onBackPressed();
                }
            }
        });
    }
}
