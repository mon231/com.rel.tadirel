package com.rel.tadirel

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Starts the server after boot and after the app is updated. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        ServerService.start(context)
    }
}
