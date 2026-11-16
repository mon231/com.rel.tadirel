package com.rel.tadirel

import android.graphics.drawable.GradientDrawable
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import org.json.JSONObject

data class DeviceRow(
    val mac: String,
    val name: String?,
    val ip: String?,
    val mid: String?,
    val reachable: Boolean,
    val paired: Boolean,
) {
    companion object {
        private fun optStringOrNull(o: JSONObject, key: String): String? =
            if (o.isNull(key) || !o.has(key)) null else o.getString(key)

        fun fromKnownJson(o: JSONObject) = DeviceRow(
            mac = o.getString("mac"),
            name = optStringOrNull(o, "name") ?: o.getString("mac"),
            ip = optStringOrNull(o, "ip"),
            mid = optStringOrNull(o, "mid"),
            reachable = o.optBoolean("reachable", false),
            paired = true,
        )

        fun fromScanJson(o: JSONObject) = DeviceRow(
            mac = o.getString("mac"),
            name = optStringOrNull(o, "name"),
            ip = o.getString("ip"),
            mid = optStringOrNull(o, "mid"),
            reachable = true,
            paired = o.optBoolean("paired", false),
        )
    }
}

enum class DeviceListMode { KNOWN, SCAN }

class DeviceAdapter(
    private val mode: DeviceListMode,
    private val onClick: (DeviceRow) -> Unit,
    private val onTrash: ((DeviceRow) -> Unit)? = null,
    private val onName: ((DeviceRow) -> Unit)? = null,
) : RecyclerView.Adapter<DeviceAdapter.ViewHolder>() {

    private val items = mutableListOf<DeviceRow>()

    fun submit(newItems: List<DeviceRow>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    fun upsert(row: DeviceRow) {
        val idx = items.indexOfFirst { it.mac == row.mac }
        if (idx >= 0) items[idx] = row else items.add(row)
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_device, parent, false)
        return ViewHolder(view)
    }

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(items[position])
    }

    inner class ViewHolder(itemView: android.view.View) : RecyclerView.ViewHolder(itemView) {
        private val row = itemView.findViewById<android.view.View>(R.id.row)
        private val dot = itemView.findViewById<android.view.View>(R.id.dot)
        private val nameText = itemView.findViewById<android.widget.TextView>(R.id.nameText)
        private val metaText = itemView.findViewById<android.widget.TextView>(R.id.metaText)
        private val nameButton = itemView.findViewById<android.widget.Button>(R.id.nameButton)
        private val trashButton = itemView.findViewById<android.widget.ImageButton>(R.id.trashButton)

        fun bind(device: DeviceRow) {
            val context = itemView.context
            val displayName = device.name ?: "Unnamed unit"
            nameText.text = if (mode == DeviceListMode.SCAN && device.paired) "$displayName (saved)" else displayName

            val macFormatted = device.mac.chunked(2).joinToString(":").uppercase()
            metaText.text = if (device.ip != null) "$macFormatted · ${device.ip}" else macFormatted

            val dotColor = if (device.reachable) R.color.accent else R.color.text_dim
            (dot.background as GradientDrawable).setColor(ContextCompat.getColor(context, dotColor))

            val grayedOut = mode == DeviceListMode.KNOWN && !device.reachable
            row.alpha = if (grayedOut) 0.45f else 1f
            row.isClickable = !grayedOut
            row.setOnClickListener { if (!grayedOut) onClick(device) }

            trashButton.visibility = if (mode == DeviceListMode.KNOWN) android.view.View.VISIBLE else android.view.View.GONE
            trashButton.setOnClickListener { onTrash?.invoke(device) }

            nameButton.visibility =
                if (mode == DeviceListMode.SCAN && !device.paired) android.view.View.VISIBLE else android.view.View.GONE
            nameButton.setOnClickListener { onName?.invoke(device) }
        }
    }
}
