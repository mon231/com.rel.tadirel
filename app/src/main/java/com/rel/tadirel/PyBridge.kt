package com.rel.tadirel

import com.chaquo.python.Python
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/**
 * Calls into app/src/main/python/android_bridge.py, which wraps the
 * shared `tadiran_ac_backend.api` module and returns JSON strings.
 * Every call runs on Dispatchers.IO -- these can block for seconds
 * (binding to a real AC unit over UDP), never call from the main thread.
 */
object PyBridge {

    class BridgeError(message: String) : Exception(message)

    private fun module() = Python.getInstance().getModule("android_bridge")

    private fun unwrap(jsonText: String): Any? {
        val obj = JSONObject(jsonText)
        if (!obj.getBoolean("ok")) {
            throw BridgeError(obj.optString("error", "unknown error"))
        }
        return obj.opt("value")
    }

    suspend fun startScan(): String = withContext(Dispatchers.IO) {
        (unwrap(module().callAttr("start_scan").toString()) as JSONObject).getString("scan_id")
    }

    suspend fun pollScan(scanId: String): JSONObject = withContext(Dispatchers.IO) {
        unwrap(module().callAttr("poll_scan", scanId).toString()) as JSONObject
    }

    suspend fun listKnownDevices(): JSONArray = withContext(Dispatchers.IO) {
        unwrap(module().callAttr("list_known_devices").toString()) as JSONArray
    }

    suspend fun setDeviceName(mac: String, ip: String, mid: String?, name: String): JSONObject =
        withContext(Dispatchers.IO) {
            unwrap(
                module().callAttr("set_device_name", mac, ip, mid, name).toString()
            ) as JSONObject
        }

    suspend fun renameDevice(mac: String, newName: String): JSONObject = withContext(Dispatchers.IO) {
        unwrap(module().callAttr("rename_device", mac, newName).toString()) as JSONObject
    }

    suspend fun removeDevice(mac: String): JSONObject = withContext(Dispatchers.IO) {
        unwrap(module().callAttr("remove_device", mac).toString()) as JSONObject
    }

    suspend fun getStatus(mac: String): JSONObject = withContext(Dispatchers.IO) {
        unwrap(module().callAttr("get_status", mac).toString()) as JSONObject
    }

    suspend fun sendCommand(mac: String, changes: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        unwrap(module().callAttr("send_command", mac, changes.toString()).toString()) as JSONObject
    }

    suspend fun capabilities(): JSONObject = withContext(Dispatchers.IO) {
        unwrap(module().callAttr("capabilities").toString()) as JSONObject
    }
}
