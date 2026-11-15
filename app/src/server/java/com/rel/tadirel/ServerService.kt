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
 * Keeps the shared backend's HTTPS server (webserver.py, port 18972) alive.
 * START_STICKY + a held CPU/Wi-Fi lock so Android keeps it running; the
 * server itself is the same Python code the PC build can run.
 */
class ServerService : Service() {

    private var cpuLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "Tadirel server", NotificationManager.IMPORTANCE_LOW)
        )
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        val notification = Notification.Builder(this, CHANNEL)
            .setContentTitle("Tadirel server running")
            .setContentText("https port $PORT")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
        startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)

        cpuLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "tadirel:server").apply { acquire() }
        wifiLock = applicationContext.getSystemService(WifiManager::class.java)
            .createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "tadirel:server").apply { acquire() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // idempotent on the Python side; off the main thread (binds a socket)
        Thread {
            Python.getInstance().getModule("android_bridge").callAttr("start_server")
        }.start()
        return START_STICKY
    }

    override fun onDestroy() {
        cpuLock?.release()
        wifiLock?.release()
        super.onDestroy()
    }

    companion object {
        const val CHANNEL = "server"
        const val PORT = 18972

        fun start(context: Context) {
            context.startForegroundService(Intent(context, ServerService::class.java))
        }
    }
}
