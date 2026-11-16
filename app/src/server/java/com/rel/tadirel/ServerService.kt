package com.rel.tadirel

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.wifi.WifiManager
import android.os.IBinder
import android.os.PowerManager
import com.chaquo.python.Python

/**
 * Keeps the shared backend's HTTPS server (webserver.py via server_config)
 * alive. START_STICKY + held CPU/Wi-Fi locks so Android keeps it running,
 * plus a watchdog thread that re-runs the idempotent start so a failed bind
 * (e.g. a configured IP not up yet right after boot) is retried forever.
 */
class ServerService : Service() {

    private var cpuLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null
    private var watchdog: Thread? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "Tadirel server", NotificationManager.IMPORTANCE_LOW)
        )
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, ServerSettingsActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        val notification = Notification.Builder(this, CHANNEL)
            .setContentTitle("Tadirel server running")
            .setContentText("Tap to change password / port")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
        startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)

        cpuLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "tadirel:server").apply { acquire() }
        @Suppress("DEPRECATION")
        wifiLock = applicationContext.getSystemService(WifiManager::class.java)
            .createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "tadirel:server").apply { acquire() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (watchdog == null) {
            watchdog = Thread {
                while (!Thread.currentThread().isInterrupted) {
                    try {
                        Python.getInstance().getModule("android_bridge").callAttr("start_server")
                        Thread.sleep(15_000)
                    } catch (e: InterruptedException) {
                        break
                    } catch (e: Exception) {
                        try { Thread.sleep(15_000) } catch (_: InterruptedException) { break }
                    }
                }
            }.also { it.start() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        watchdog?.interrupt()
        cpuLock?.release()
        wifiLock?.release()
        super.onDestroy()
    }

    companion object {
        const val CHANNEL = "server"

        fun start(context: Context) {
            context.startForegroundService(Intent(context, ServerService::class.java))
        }
    }
}
