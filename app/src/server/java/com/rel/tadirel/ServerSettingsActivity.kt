package com.rel.tadirel

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

/**
 * The server build's only screen: edit the HTTPS server's listen address,
 * port and password. Opening it also (re)starts the always-on service.
 */
class ServerSettingsActivity : AppCompatActivity() {

    private lateinit var host: EditText
    private lateinit var port: EditText
    private lateinit var password: EditText
    private lateinit var status: TextView

    private fun LinearLayout.field(label: String, type: Int): EditText {
        addView(TextView(context).apply { text = label; setPadding(0, 32, 0, 0); setTextColor(context.getColor(R.color.text_dim)) })
        return EditText(context).apply {
            inputType = type
            setTextColor(context.getColor(R.color.text_main))
            setSingleLine()
            this@field.addView(this)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pad = (20 * resources.displayMetrics.density).toInt()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad * 3, pad, pad)
        }
        root.addView(TextView(this).apply { text = "Tadirel Server"; textSize = 24f; setTextColor(context.getColor(R.color.text_main)) })
        host = root.field("Listen address (0.0.0.0 = all interfaces)", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI)
        port = root.field("Port", InputType.TYPE_CLASS_NUMBER)
        password = root.field("Password", InputType.TYPE_CLASS_TEXT)
        root.addView(Button(this).apply {
            text = "Save"
            setBackgroundColor(context.getColor(R.color.accent))
            setTextColor(context.getColor(R.color.bg))
            setOnClickListener { save() }
        })
        status = TextView(this).apply { setPadding(0, 32, 0, 0); setTextColor(context.getColor(R.color.text_main)) }
        root.addView(status)
        setContentView(root)

        ServerService.start(this)
        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        if (!getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(packageName)) {
            startActivity(
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                    .setData(Uri.parse("package:$packageName"))
            )
        }

        lifecycleScope.launch {
            val s = PyBridge.getServerSettings()
            host.setText(s.getString("host"))
            port.setText(s.getInt("port").toString())
            password.setText(s.getString("password"))
            refreshStatus()
        }
    }

    private fun save() {
        lifecycleScope.launch {
            try {
                PyBridge.setServerSettings(host.text.toString(), port.text.toString(), password.text.toString())
                refreshStatus("Saved. ")
            } catch (e: PyBridge.BridgeError) {
                status.text = "Not saved: ${e.message}"
            }
        }
    }

    private suspend fun refreshStatus(prefix: String = "") {
        val st = PyBridge.serverStatus()
        status.text = prefix + if (st.optBoolean("running")) {
            "Running on port ${st.getInt("port")}"
        } else {
            "Not running: ${st.optString("error", "starting...")}"
        }
    }
}
