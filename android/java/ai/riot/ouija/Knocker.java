package ai.riot.ouija;

import android.content.Context;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.webkit.JavascriptInterface;

/**
 * The bridge the board uses to knock back through the phone.
 *
 * Top-level on purpose: this is the only thing the page can reach, and a flat
 * class keeps the surface obvious — one method, one bounded argument.
 */
public class Knocker {

    private final Context ctx;

    Knocker(Context ctx) {
        this.ctx = ctx;
    }

    /** A short tap under the fingers when the planchette lands on a letter. */
    @JavascriptInterface
    public void knock(int ms) {
        if (ms <= 0 || ms > 400) ms = 18;
        Vibrator v = (Vibrator) ctx.getSystemService(Context.VIBRATOR_SERVICE);
        if (v == null || !v.hasVibrator()) return;
        if (Build.VERSION.SDK_INT >= 26) {
            v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE));
        } else {
            v.vibrate(ms);
        }
    }
}
