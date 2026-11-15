package com.rel.tadirel

import android.content.Intent
import android.os.Bundle
import android.text.InputType
import android.view.View
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var knownAdapter: DeviceAdapter
    private lateinit var scanAdapter: DeviceAdapter
    private lateinit var knownEmptyHint: View
    private lateinit var scanProgressBar: ProgressBar
    private lateinit var scanProgressLabel: TextView

    private val scanTotalSeconds = 12

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        applyEdgeToEdgeInsets(findViewById(android.R.id.content))

        knownEmptyHint = findViewById(R.id.knownEmptyHint)
        scanProgressBar = findViewById(R.id.scanProgressBar)
        scanProgressLabel = findViewById(R.id.scanProgressLabel)

        knownAdapter = DeviceAdapter(
            mode = DeviceListMode.KNOWN,
            onClick = { row -> openDetail(row) },
            onTrash = { row -> confirmRemove(row) },
        )
        findViewById<RecyclerView>(R.id.knownRecyclerView).apply {
            layoutManager = LinearLayoutManager(this@MainActivity)
            adapter = knownAdapter
        }

        scanAdapter = DeviceAdapter(
            mode = DeviceListMode.SCAN,
            onClick = { row -> if (row.paired) openDetail(row) },
            onName = { row -> promptName(row) },
        )
        findViewById<RecyclerView>(R.id.scanRecyclerView).apply {
            layoutManager = LinearLayoutManager(this@MainActivity)
            adapter = scanAdapter
        }

        findViewById<View>(R.id.refreshKnownButton).setOnClickListener { loadKnown() }
        findViewById<View>(R.id.scanButton).setOnClickListener { startScan() }

        loadKnown()
    }

    override fun onResume() {
        super.onResume()
        loadKnown()
    }

    private fun loadKnown() {
        lifecycleScope.launch {
            try {
                val arr = PyBridge.listKnownDevices()
                val rows = (0 until arr.length()).map { DeviceRow.fromKnownJson(arr.getJSONObject(it)) }
                knownAdapter.submit(rows)
                knownEmptyHint.visibility = if (rows.isEmpty()) View.VISIBLE else View.GONE
            } catch (e: PyBridge.BridgeError) {
                toast(e.message ?: "failed to load saved devices")
            }
        }
    }

    private fun startScan() {
        val button = findViewById<View>(R.id.scanButton)
        button.isEnabled = false
        scanAdapter.submit(emptyList())
        scanProgressBar.visibility = View.VISIBLE
        scanProgressLabel.visibility = View.VISIBLE

        lifecycleScope.launch {
            val scanId = try {
                PyBridge.startScan()
            } catch (e: PyBridge.BridgeError) {
                toast(e.message ?: "scan failed to start")
                button.isEnabled = true
                return@launch
            }

            val startedAt = System.currentTimeMillis()
            while (true) {
                val elapsedSec = ((System.currentTimeMillis() - startedAt) / 1000).toInt()
                scanProgressBar.progress = elapsedSec.coerceAtMost(scanTotalSeconds)
                scanProgressLabel.text = "Scanning… ${elapsedSec.coerceAtMost(scanTotalSeconds)}s / ${scanTotalSeconds}s"

                val result = try {
                    PyBridge.pollScan(scanId)
                } catch (e: PyBridge.BridgeError) {
                    toast(e.message ?: "scan error")
                    break
                }

                val newArr = result.getJSONArray("new")
                for (i in 0 until newArr.length()) {
                    scanAdapter.upsert(DeviceRow.fromScanJson(newArr.getJSONObject(i)))
                }

                if (result.getBoolean("done")) {
                    scanProgressLabel.text = "Done"
                    break
                }
                delay(350)
            }

            button.isEnabled = true
            delay(1200)
            scanProgressBar.visibility = View.GONE
            scanProgressLabel.visibility = View.GONE
        }
    }

    private fun promptName(row: DeviceRow) {
        val input = EditText(this).apply { inputType = InputType.TYPE_CLASS_TEXT }
        AlertDialog.Builder(this)
            .setTitle("Name this air conditioner")
            .setView(input)
            .setPositiveButton("Save") { _, _ ->
                val name = input.text.toString().trim()
                if (name.isEmpty()) return@setPositiveButton
                lifecycleScope.launch {
                    try {
                        PyBridge.setDeviceName(row.mac, row.ip ?: "", row.mid, name)
                        toast("Saved \"$name\"")
                        loadKnown()
                    } catch (e: PyBridge.BridgeError) {
                        toast(e.message ?: "failed to save")
                    }
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun confirmRemove(row: DeviceRow) {
        AlertDialog.Builder(this)
            .setTitle("Remove \"${row.name}\"?")
            .setMessage("This only removes the saved name/pairing, not any settings on the unit itself.")
            .setPositiveButton("Remove") { _, _ ->
                lifecycleScope.launch {
                    try {
                        PyBridge.removeDevice(row.mac)
                        loadKnown()
                    } catch (e: PyBridge.BridgeError) {
                        toast(e.message ?: "failed to remove")
                    }
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun openDetail(row: DeviceRow) {
        if (!row.reachable) return
        startActivity(
            Intent(this, DeviceDetailActivity::class.java)
                .putExtra(DeviceDetailActivity.EXTRA_MAC, row.mac)
                .putExtra(DeviceDetailActivity.EXTRA_NAME, row.name ?: row.mac)
        )
    }

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
}
