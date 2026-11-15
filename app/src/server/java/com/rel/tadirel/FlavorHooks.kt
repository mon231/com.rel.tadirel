package com.rel.tadirel

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings

/** Server flavor: opening the app (re)starts the service and asks, once per
 *  launch until granted, for the permissions that keep it alive. */
object FlavorHooks {
    fun onMainActivity(activity: Activity) {
        ServerService.start(activity)
        if (Build.VERSION.SDK_INT >= 33) {
            activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        val pm = activity.getSystemService(PowerManager::class.java)
        if (!pm.isIgnoringBatteryOptimizations(activity.packageName)) {
            activity.startActivity(
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                    .setData(Uri.parse("package:${activity.packageName}"))
            )
        }
    }
}
