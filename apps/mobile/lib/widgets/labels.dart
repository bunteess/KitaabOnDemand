import '../core/pricing.dart';
import '../data/models.dart';
import '../l10n/generated/app_localizations.dart';

String paperLabel(AppLocalizations l, Paper paper) => switch (paper) {
  Paper.localWhite => l.paperLocalWhite,
  Paper.importedYellow => l.paperImportedYellow,
};

String bindingLabel(AppLocalizations l, Binding binding) => switch (binding) {
  Binding.softcoverPaperback => l.bindingSoftcover,
  Binding.premiumHardcover => l.bindingHardcover,
};

String paymentLabel(AppLocalizations l, PaymentMethod method) =>
    switch (method) {
      PaymentMethod.cod => l.payCod,
      PaymentMethod.easypaisa => l.payEasypaisa,
      PaymentMethod.jazzcash => l.payJazzcash,
      PaymentMethod.card => l.payCard,
    };

String paymentStatusLabel(AppLocalizations l, PaymentStatus status) =>
    switch (status) {
      PaymentStatus.pending => l.paymentPending,
      PaymentStatus.paid => l.paymentPaid,
      PaymentStatus.failed => l.paymentFailedStatus,
      PaymentStatus.refunded => l.paymentRefunded,
    };

String statusLabel(AppLocalizations l, OrderStatus status) => switch (status) {
  OrderStatus.pendingPayment => l.statusPendingPayment,
  OrderStatus.placed => l.statusPlaced,
  OrderStatus.verifying => l.statusVerifying,
  OrderStatus.assigned => l.statusAssigned,
  OrderStatus.inPrint => l.statusInPrint,
  OrderStatus.readyForDispatch => l.statusReadyForDispatch,
  OrderStatus.dispatched => l.statusDispatched,
  OrderStatus.delivered => l.statusDelivered,
  OrderStatus.completed => l.statusCompleted,
  OrderStatus.rejected => l.statusRejected,
  OrderStatus.cancelled => l.statusCancelled,
  OrderStatus.deliveryFailed => l.statusDeliveryFailed,
  OrderStatus.requested => l.statusRequested,
  OrderStatus.quoted => l.statusQuoted,
  OrderStatus.accepted => l.statusAccepted,
  OrderStatus.sourcing => l.statusSourcing,
  OrderStatus.quoteExpired => l.statusQuoteExpired,
  OrderStatus.declined => l.statusDeclined,
  OrderStatus.unavailable => l.statusUnavailable,
};

String stepLabel(AppLocalizations l, TimelineStep step, OrderType type) =>
    switch (step) {
      TimelineStep.placed => l.stepPlaced,
      TimelineStep.verifying =>
        type == OrderType.source ? l.stepSourcing : l.stepVerifying,
      TimelineStep.printing => l.stepPrinting,
      TimelineStep.outForDelivery => l.stepOutForDelivery,
      TimelineStep.completed => l.stepCompleted,
    };

String exitLabel(AppLocalizations l, OrderStatus status) => switch (status) {
  OrderStatus.rejected => l.exitRejected,
  OrderStatus.quoteExpired => l.exitQuoteExpired,
  OrderStatus.declined => l.exitDeclined,
  OrderStatus.unavailable => l.exitUnavailable,
  OrderStatus.deliveryFailed => l.exitDeliveryFailed,
  _ => l.exitCancelled,
};

String rejectionLabel(AppLocalizations l, String? code) => switch (code) {
  'CORRUPT' || 'NOT_PDF' => l.rejectCorrupt,
  'ENCRYPTED' => l.rejectEncrypted,
  'NO_PAGES' => l.rejectNoPages,
  'ACTIVE_CONTENT' => l.rejectActiveContent,
  'TOO_LARGE' || 'SIZE_MISMATCH' => l.rejectTooLarge,
  'MALWARE' => l.rejectMalware,
  _ => l.rejectGeneric,
};

/// 157286400 -> "150 MB"
String formatBytes(int bytes) {
  const mb = 1024 * 1024;
  if (bytes >= mb) {
    return '${(bytes / mb).toStringAsFixed(bytes >= 10 * mb ? 0 : 1)} MB';
  }
  return '${(bytes / 1024).ceil()} KB';
}
