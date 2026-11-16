package com.rel.tadirel

import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/**
 * targetSdk 35 draws edge-to-edge by default -- without this, content sits
 * under the status/navigation bars and gets clipped or overlapped (the
 * "ugly fixed-size" look). Pads [target] by the system bar insets instead
 * so every screen fills whatever window size it's actually given.
 */
fun applyEdgeToEdgeInsets(target: View) {
    ViewCompat.setOnApplyWindowInsetsListener(target) { view, windowInsets ->
        val bars = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
        view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
        WindowInsetsCompat.CONSUMED
    }
}
