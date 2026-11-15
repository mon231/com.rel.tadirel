package com.rel.tadirel

import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.isVisible
import androidx.lifecycle.lifecycleScope
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import com.google.android.material.switchmaterial.SwitchMaterial
import kotlinx.coroutines.launch
import org.json.JSONObject

class DeviceDetailActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_MAC = "mac"
        const val EXTRA_NAME = "name"
    }

    private lateinit var mac: String
    private lateinit var nameText: TextView
    private lateinit var metaText: TextView
    private lateinit var progress: View
    private lateinit var container: LinearLayout
    private var currentStatus: JSONObject = JSONObject()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_device_detail)
        applyEdgeToEdgeInsets(findViewById(android.R.id.content))

        mac = intent.getStringExtra(EXTRA_MAC) ?: run { finish(); return }
        nameText = findViewById(R.id.deviceNameText)
        metaText = findViewById(R.id.deviceMetaText)
        progress = findViewById(R.id.detailProgress)
        container = findViewById(R.id.controlsContainer)

        nameText.text = intent.getStringExtra(EXTRA_NAME) ?: mac
        metaText.text = formatMac(mac)

        findViewById<View>(R.id.closeButton).setOnClickListener { finish() }
        findViewById<View>(R.id.editButton).setOnClickListener { promptRename() }

        loadStatus()
    }

    private fun formatMac(mac: String) = mac.chunked(2).joinToString(":").uppercase()

    private fun loadStatus() {
        progress.isVisible = true
        container.removeAllViews()
        lifecycleScope.launch {
            try {
                val caps = PyBridge.capabilities()
                val statusResult = PyBridge.getStatus(mac)
                metaText.text = "${formatMac(mac)} · ${statusResult.getString("ip")}"
                currentStatus = statusResult.getJSONObject("status")
                renderControls(caps)
            } catch (e: PyBridge.BridgeError) {
                toast(e.message ?: "failed to load status")
            } finally {
                progress.isVisible = false
            }
        }
    }

    private fun renderControls(caps: JSONObject) {
        container.removeAllViews()
        val controls = caps.getJSONArray("controls")
        for (i in 0 until controls.length()) {
            container.addView(buildControlRow(controls.getJSONObject(i)))
        }
        val readonly = caps.getJSONArray("readonly")
        for (i in 0 until readonly.length()) {
            container.addView(buildReadonlyRow(readonly.getJSONObject(i)))
        }
    }

    private fun rowContainer(): LinearLayout {
        val row = LinearLayout(this)
        row.orientation = LinearLayout.VERTICAL
        row.setBackgroundResource(R.drawable.bg_device_row)
        val pad = dp(12)
        row.setPadding(pad, pad, pad, pad)
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.bottomMargin = dp(10)
        row.layoutParams = lp
        return row
    }

    private fun labelRow(text: String, valueText: String? = null): LinearLayout {
        val line = LinearLayout(this)
        line.orientation = LinearLayout.HORIZONTAL
        line.gravity = Gravity.CENTER_VERTICAL
        val label = TextView(this)
        label.text = text
        label.setTextColor(ContextCompat.getColor(this, R.color.text_main))
        label.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        line.addView(label)
        if (valueText != null) {
            val value = TextView(this)
            value.text = valueText
            value.setTextColor(ContextCompat.getColor(this, R.color.text_dim))
            line.addView(value)
        }
        return line
    }

    private fun buildReadonlyRow(spec: JSONObject): View {
        val row = rowContainer()
        val value = currentStatus.opt(spec.getString("key"))
        val display = if (value == null || value == JSONObject.NULL) "—" else "$value°C"
        row.addView(labelRow(spec.getString("label"), display))
        return row
    }

    private fun buildControlRow(spec: JSONObject): View {
        val key = spec.getString("key")
        val kind = spec.getString("kind")
        val row = rowContainer()

        when (kind) {
            "toggle" -> {
                val line = LinearLayout(this)
                line.orientation = LinearLayout.HORIZONTAL
                line.gravity = Gravity.CENTER_VERTICAL
                val label = TextView(this)
                label.text = spec.getString("label")
                label.setTextColor(ContextCompat.getColor(this, R.color.text_main))
                label.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                line.addView(label)

                val switch = SwitchMaterial(this)
                val current = currentStatus.optBoolean(key, false)
                switch.isChecked = current
                switch.setOnCheckedChangeListener { _, isChecked ->
                    sendChange(JSONObject().put(key, if (isChecked) 1 else 0))
                }
                line.addView(switch)
                row.addView(line)
            }

            "enum" -> {
                row.addView(labelRow(spec.getString("label")))
                val chipGroup = ChipGroup(this)
                chipGroup.isSingleSelection = true
                val choices = spec.getJSONArray("choices")
                val currentValue = currentStatus.optInt(key, Int.MIN_VALUE)
                for (i in 0 until choices.length()) {
                    val choice = choices.getJSONObject(i)
                    val chip = Chip(this)
                    chip.text = choice.getString("label")
                    chip.isCheckable = true
                    chip.isChecked = choice.getInt("value") == currentValue
                    chip.setOnClickListener {
                        sendChange(JSONObject().put(key, choice.getInt("value")))
                    }
                    chipGroup.addView(chip)
                }
                row.addView(chipGroup)
            }

            "int_range" -> {
                row.addView(labelRow(spec.getString("label")))
                val stepper = LinearLayout(this)
                stepper.orientation = LinearLayout.HORIZONTAL
                stepper.gravity = Gravity.CENTER
                val min = spec.optInt("min", 8)
                val max = spec.optInt("max", 30)
                val current = currentStatus.optInt(key, min)

                val decButton = Button(this)
                decButton.text = "−"
                val valueText = TextView(this)
                valueText.text = "$current°C"
                valueText.textSize = 20f
                valueText.setTextColor(ContextCompat.getColor(this, R.color.text_main))
                valueText.gravity = Gravity.CENTER
                valueText.setPadding(dp(16), 0, dp(16), 0)
                val incButton = Button(this)
                incButton.text = "+"

                decButton.setOnClickListener {
                    val next = (current - 1).coerceAtLeast(min)
                    sendChange(JSONObject().put(key, next))
                }
                incButton.setOnClickListener {
                    val next = (current + 1).coerceAtMost(max)
                    sendChange(JSONObject().put(key, next))
                }

                stepper.addView(decButton)
                stepper.addView(valueText)
                stepper.addView(incButton)
                row.addView(stepper)
            }
        }
        return row
    }

    private fun sendChange(changes: JSONObject) {
        // send_command blocks (on the IO dispatcher) until the AC's own
        // status confirms the change, or ~7s elapse -- the spinner stays
        // up for that whole wait so the UI never claims success before
        // the unit actually reports it.
        progress.isVisible = true
        setContainerEnabled(false)
        lifecycleScope.launch {
            try {
                val result = PyBridge.sendCommand(mac, changes)
                currentStatus = result.getJSONObject("status")
                val caps = PyBridge.capabilities()
                renderControls(caps)
                if (!result.optBoolean("confirmed", true)) {
                    toast("Sent, but the AC hasn't confirmed the change yet — showing its latest real status.")
                }
            } catch (e: PyBridge.BridgeError) {
                toast(e.message ?: "command failed")
            } finally {
                progress.isVisible = false
                setContainerEnabled(true)
            }
        }
    }

    private fun setContainerEnabled(enabled: Boolean) {
        container.alpha = if (enabled) 1f else 0.55f
        fun walk(v: View) {
            v.isEnabled = enabled
            if (v is ViewGroup) for (i in 0 until v.childCount) walk(v.getChildAt(i))
        }
        walk(container)
    }

    private fun promptRename() {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT
            setText(nameText.text)
        }
        AlertDialog.Builder(this)
            .setTitle("Rename")
            .setView(input)
            .setPositiveButton("Save") { _, _ ->
                val newName = input.text.toString().trim()
                if (newName.isEmpty()) return@setPositiveButton
                lifecycleScope.launch {
                    try {
                        PyBridge.renameDevice(mac, newName)
                        nameText.text = newName
                    } catch (e: PyBridge.BridgeError) {
                        toast(e.message ?: "rename failed")
                    }
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
}
