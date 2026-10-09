package pk.kitaabondemand.kitaab_app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createOrderUpdatesChannel()
    }

    // Firebase shows push notifications on this channel (AndroidManifest.xml
    // default_notification_channel_id). Creating it again is a no-op.
    private fun createOrderUpdatesChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            "order_updates",
            getString(R.string.notification_channel_orders),
            NotificationManager.IMPORTANCE_HIGH,
        )
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}
