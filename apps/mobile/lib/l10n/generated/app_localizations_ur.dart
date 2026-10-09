// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Urdu (`ur`).
class AppLocalizationsUr extends AppLocalizations {
  AppLocalizationsUr([String locale = 'ur']) : super(locale);

  @override
  String get appTitle => 'کتاب آن ڈیمانڈ';

  @override
  String get retry => 'Try again';

  @override
  String get cancel => 'Cancel';

  @override
  String get confirm => 'Confirm';

  @override
  String get continueLabel => 'Continue';

  @override
  String get save => 'Save';

  @override
  String get delete => 'Delete';

  @override
  String get edit => 'Edit';

  @override
  String get close => 'Close';

  @override
  String get ok => 'OK';

  @override
  String get errorGeneric => 'Something went wrong. Please try again.';

  @override
  String get errorOffline =>
      'You are offline. Check your connection and try again.';

  @override
  String get errorTimeout =>
      'This is taking too long. Check your connection and try again.';

  @override
  String get errorSessionExpired => 'Please sign in again.';

  @override
  String get errorRateLimited =>
      'Too many attempts. Please wait a few minutes and try again.';

  @override
  String get offlineBanner => 'You are offline';

  @override
  String get optional => 'Optional';

  @override
  String get fieldRequired => 'This field is required';

  @override
  String get onboardingTitle1 => 'Find any book';

  @override
  String get onboardingBody1 =>
      'Tell us the book you need. We find it and send you a price.';

  @override
  String get onboardingTitle2 => 'Print your PDF';

  @override
  String get onboardingBody2 =>
      'Upload a PDF, choose paper and binding, and we print it.';

  @override
  String get onboardingTitle3 => 'Delivered to your door';

  @override
  String get onboardingBody3 =>
      'Pay cash on delivery or online, and track every step.';

  @override
  String get onboardingSkip => 'Skip';

  @override
  String get onboardingNext => 'Next';

  @override
  String get onboardingStart => 'Get started';

  @override
  String get loginTitle => 'Sign in';

  @override
  String get loginPhoneLabel => 'Mobile number';

  @override
  String get loginPhoneHint => '0300 1234567';

  @override
  String get loginSendCode => 'Send code';

  @override
  String get loginWithGoogle => 'Continue with Google';

  @override
  String get loginOr => 'or';

  @override
  String get loginTermsNotice =>
      'By continuing you agree to our Terms of Service and Privacy Policy.';

  @override
  String get phoneInvalid =>
      'Enter a Pakistani mobile number, for example 0300 1234567';

  @override
  String get otpTitle => 'Enter the code';

  @override
  String otpSentTo(String phone) {
    return 'We sent a 6-digit code to $phone';
  }

  @override
  String get otpCodeLabel => '6-digit code';

  @override
  String otpResendIn(int seconds) {
    return 'Send a new code in ${seconds}s';
  }

  @override
  String get otpResend => 'Send a new code';

  @override
  String get otpChangeNumber => 'Change number';

  @override
  String get otpVerify => 'Verify';

  @override
  String otpWrong(int attempts) {
    return 'Wrong code. $attempts attempts left.';
  }

  @override
  String get otpWrongNoCount => 'Wrong code. Please check and try again.';

  @override
  String get otpExpired => 'This code has expired. Send a new one.';

  @override
  String get otpTooMany => 'Too many attempts. Send a new code later.';

  @override
  String get googleSignInFailed =>
      'Google sign-in did not finish. Try again or use your mobile number.';

  @override
  String get googleNotConfigured =>
      'Google sign-in is not available in this build.';

  @override
  String get termsTitle => 'Before you start';

  @override
  String get termsSummary =>
      'Please read and accept our Terms of Service and Privacy Policy. They explain how we handle your orders, files and personal details.';

  @override
  String get termsAgree => 'I agree to the Terms of Service and Privacy Policy';

  @override
  String get termsOfService => 'Terms of Service';

  @override
  String get privacyPolicy => 'Privacy Policy';

  @override
  String get addPhoneTitle => 'Add your mobile number';

  @override
  String get addPhoneBody =>
      'We need a verified mobile number before your first order, for delivery updates and the courier.';

  @override
  String get phoneInUse =>
      'This number is already used by another account. Contact support for help.';

  @override
  String get navHome => 'Home';

  @override
  String get navOrders => 'Orders';

  @override
  String get navInbox => 'Inbox';

  @override
  String get navProfile => 'Profile';

  @override
  String homeGreeting(String name) {
    return 'Hello, $name';
  }

  @override
  String get homeGreetingNoName => 'Hello';

  @override
  String get homeFindBookTitle => 'Find a book';

  @override
  String get homeFindBookBody => 'We find it and send you a price';

  @override
  String get homePrintTitle => 'Print my PDF';

  @override
  String get homePrintBody => 'Upload a file, we print and bind it';

  @override
  String get homeCalculator => 'Price calculator';

  @override
  String get homeLatestOrder => 'Your latest order';

  @override
  String get homeSeeAll => 'See all orders';

  @override
  String get notificationsTooltip => 'Notifications';

  @override
  String get requestTitle => 'Find a book';

  @override
  String get fieldBookTitle => 'Book title';

  @override
  String get fieldAuthor => 'Author';

  @override
  String get fieldIsbn => 'ISBN';

  @override
  String get fieldEdition => 'Edition';

  @override
  String get fieldNotes => 'Anything else we should know';

  @override
  String get fieldCopies => 'Copies';

  @override
  String get fieldPreferredPaper => 'Preferred paper';

  @override
  String get fieldPreferredBinding => 'Preferred binding';

  @override
  String get noPreference => 'No preference';

  @override
  String get fieldDeliveryAddress => 'Delivery address';

  @override
  String get addAddress => 'Add address';

  @override
  String get changeAddress => 'Change';

  @override
  String get requestSubmit => 'Send request';

  @override
  String get requestSubmitted =>
      'We are looking for your book. We will send you a price soon.';

  @override
  String copiesRange(int max) {
    return 'Choose between 1 and $max copies';
  }

  @override
  String get paperLocalWhite => 'Local White';

  @override
  String get paperImportedYellow => 'Imported Yellow';

  @override
  String get bindingSoftcover => 'Softcover Paperback';

  @override
  String get bindingHardcover => 'Premium Hardcover';

  @override
  String get fieldPaper => 'Paper';

  @override
  String get fieldBinding => 'Binding';

  @override
  String get fieldPages => 'Number of pages';

  @override
  String get fieldCity => 'Delivery city';

  @override
  String get printTitle => 'Print my PDF';

  @override
  String get printIntro =>
      'Choose a PDF up to 150 MB. We check every file before printing.';

  @override
  String get printPickFile => 'Choose PDF';

  @override
  String get printChangeFile => 'Choose another file';

  @override
  String printPagesFound(int pages) {
    return '$pages pages';
  }

  @override
  String get printPagesManual =>
      'We could not read the page count. Enter it below and we will check it after upload.';

  @override
  String get printCopyright =>
      'I own this file or have permission to print it.';

  @override
  String get printTooLarge =>
      'This file is larger than 150 MB. Please choose a smaller file.';

  @override
  String get printNotPdf => 'Please choose a PDF file.';

  @override
  String get printPickFailed =>
      'The file could not be opened. Please try another file.';

  @override
  String get pagesInvalid => 'Enter the number of pages';

  @override
  String get optionsTitle => 'Print options';

  @override
  String get uploadAndContinue => 'Upload and continue';

  @override
  String pagesExceedBinding(int max) {
    return 'This binding allows up to $max pages. Please choose another binding.';
  }

  @override
  String get cityNotServed => 'We do not deliver to this city yet.';

  @override
  String get priceUnavailable => 'Prices could not be loaded.';

  @override
  String get priceTitle => 'Price';

  @override
  String pricePrinting(int pages, int copies) {
    return 'Printing ($pages pages × $copies)';
  }

  @override
  String priceBinding(int copies) {
    return 'Binding × $copies';
  }

  @override
  String get priceSourcing => 'Finding the book';

  @override
  String get priceRounding => 'Rounding';

  @override
  String get priceDelivery => 'Delivery';

  @override
  String get priceCodFee => 'Cash on delivery fee';

  @override
  String get priceTotal => 'Total';

  @override
  String get priceGoods => 'Book and printing';

  @override
  String get uploadTitle => 'Uploading your file';

  @override
  String uploadProgress(String sent, String total) {
    return '$sent of $total';
  }

  @override
  String get uploadPaused => 'Paused';

  @override
  String get uploadWaitingNetwork =>
      'Waiting for connection. Your upload will continue.';

  @override
  String get uploadChecking => 'Checking your file…';

  @override
  String get uploadReady => 'Your file is ready';

  @override
  String get uploadPause => 'Pause';

  @override
  String get uploadResume => 'Resume';

  @override
  String get uploadStarting => 'Preparing upload…';

  @override
  String get uploadRejectedTitle => 'We cannot print this file';

  @override
  String get rejectCorrupt => 'The file is damaged or is not a real PDF.';

  @override
  String get rejectEncrypted =>
      'The file is password-protected. Remove the password and try again.';

  @override
  String get rejectNoPages => 'The file has no pages.';

  @override
  String get rejectActiveContent =>
      'The file contains scripts or attachments, which we cannot accept.';

  @override
  String get rejectTooLarge => 'The file is larger than 150 MB.';

  @override
  String get rejectMalware => 'The file failed our safety check.';

  @override
  String get rejectGeneric =>
      'The file could not be checked. Please try again.';

  @override
  String get pageMismatchTitle => 'Page count updated';

  @override
  String pageMismatchBody(int pages, int localPages, String price) {
    return 'Your file has $pages pages, not $localPages. The new total is $price.';
  }

  @override
  String get leaveUploadTitle => 'Leave this screen?';

  @override
  String get leaveUploadBody =>
      'Your upload will keep going and you can come back to it.';

  @override
  String get leave => 'Leave';

  @override
  String get stay => 'Stay';

  @override
  String resumeUploadBanner(String file) {
    return 'You have an unfinished upload: $file';
  }

  @override
  String get resumeUploadAction => 'Continue';

  @override
  String get checkoutTitle => 'Checkout';

  @override
  String get orderSummary => 'Order summary';

  @override
  String get paymentMethodTitle => 'Payment method';

  @override
  String get payCod => 'Cash on delivery';

  @override
  String get payEasypaisa => 'Easypaisa';

  @override
  String get payJazzcash => 'JazzCash';

  @override
  String get payCard => 'Debit or credit card';

  @override
  String codNotAllowed(String amount) {
    return 'Cash on delivery is not available for orders above $amount.';
  }

  @override
  String get placeOrder => 'Place order';

  @override
  String get priceChangedTitle => 'Price updated';

  @override
  String priceChangedBody(String price) {
    return 'The total is now $price. Do you want to continue?';
  }

  @override
  String get noAddressYet => 'Add a delivery address to continue.';

  @override
  String get paymentChecking => 'Checking your payment…';

  @override
  String get paymentSuccess => 'Payment received';

  @override
  String get paymentFailed => 'The payment did not go through.';

  @override
  String get paymentChooseOther => 'Choose another method';

  @override
  String get payNow => 'Pay now';

  @override
  String get awaitingPayment => 'Awaiting payment';

  @override
  String get openPaymentPage => 'Open payment page';

  @override
  String get paymentPageNotOpened => 'The payment page could not be opened.';

  @override
  String get calculatorTitle => 'Price calculator';

  @override
  String get calculatorHint =>
      'Prices are estimates. We confirm the page count when you upload your file.';

  @override
  String get ordersTitle => 'My orders';

  @override
  String get ordersActive => 'Active';

  @override
  String get ordersPast => 'Past';

  @override
  String get ordersEmpty => 'No orders yet';

  @override
  String get ordersEmptyBody => 'Find a book or print your PDF to get started.';

  @override
  String orderCode(String code) {
    return 'Order $code';
  }

  @override
  String get needsAction => 'Action needed';

  @override
  String get loadMore => 'Load more';

  @override
  String get statusPendingPayment => 'Awaiting payment';

  @override
  String get statusPlaced => 'Placed';

  @override
  String get statusVerifying => 'Being checked';

  @override
  String get statusAssigned => 'Sent to printer';

  @override
  String get statusInPrint => 'Printing';

  @override
  String get statusReadyForDispatch => 'Ready to ship';

  @override
  String get statusDispatched => 'Out for delivery';

  @override
  String get statusDelivered => 'Delivered';

  @override
  String get statusCompleted => 'Completed';

  @override
  String get statusRejected => 'Not accepted';

  @override
  String get statusCancelled => 'Cancelled';

  @override
  String get statusDeliveryFailed => 'Delivery failed';

  @override
  String get statusRequested => 'Looking for book';

  @override
  String get statusQuoted => 'Quote ready';

  @override
  String get statusAccepted => 'Quote accepted';

  @override
  String get statusSourcing => 'Getting your book';

  @override
  String get statusQuoteExpired => 'Quote expired';

  @override
  String get statusDeclined => 'Declined';

  @override
  String get statusUnavailable => 'Not available';

  @override
  String get stepPlaced => 'Order placed';

  @override
  String get stepVerifying => 'Verifying';

  @override
  String get stepSourcing => 'Sourcing';

  @override
  String get stepPrinting => 'Printing';

  @override
  String get stepOutForDelivery => 'Out for delivery';

  @override
  String get stepCompleted => 'Completed';

  @override
  String get exitRejected => 'Your file was not accepted';

  @override
  String get exitCancelled => 'This order was cancelled';

  @override
  String get exitQuoteExpired => 'This quote has expired';

  @override
  String get exitDeclined => 'You declined this quote';

  @override
  String get exitUnavailable => 'We could not find this book';

  @override
  String get exitDeliveryFailed => 'The delivery did not succeed';

  @override
  String exitReason(String reason) {
    return 'Reason: $reason';
  }

  @override
  String get requestAgain => 'Request again';

  @override
  String get orderDetailTitle => 'Order details';

  @override
  String get quoteTitle => 'Your quote';

  @override
  String quoteValidUntil(String time) {
    return 'Valid until $time';
  }

  @override
  String quoteFor(int pages, String paper, String binding, int copies) {
    return '$pages pages, $paper, $binding, $copies copies';
  }

  @override
  String quoteTotalDigital(String amount) {
    return 'Pay online: $amount';
  }

  @override
  String quoteTotalCod(String amount) {
    return 'Cash on delivery: $amount';
  }

  @override
  String get quoteAccept => 'Accept and order';

  @override
  String get quoteDecline => 'Decline';

  @override
  String get quoteDeclineConfirm => 'Decline this quote?';

  @override
  String get quoteChoosePayment => 'How would you like to pay?';

  @override
  String get trackingTitle => 'Tracking';

  @override
  String get trackingCourier => 'Courier';

  @override
  String get trackingCn => 'Tracking number';

  @override
  String get trackingOpen => 'Track parcel';

  @override
  String get deliveryAddressTitle => 'Delivery address';

  @override
  String landmarkPrefix(String landmark) {
    return 'Near: $landmark';
  }

  @override
  String get paymentTitle => 'Payment';

  @override
  String get paymentPending => 'Pending';

  @override
  String get paymentPaid => 'Paid';

  @override
  String get paymentFailedStatus => 'Failed';

  @override
  String get paymentRefunded => 'Refunded';

  @override
  String get cancelOrder => 'Cancel order';

  @override
  String get cancelOrderConfirm => 'Cancel this order? This cannot be undone.';

  @override
  String get fileTitle => 'File';

  @override
  String get bookSection => 'Book';

  @override
  String get optionsSection => 'Options';

  @override
  String byAuthor(String author) {
    return 'by $author';
  }

  @override
  String get inboxTitle => 'Notifications';

  @override
  String get inboxEmpty => 'No notifications yet';

  @override
  String get markAllRead => 'Mark all read';

  @override
  String get profileTitle => 'Profile';

  @override
  String get profileName => 'Name';

  @override
  String get profilePhone => 'Mobile number';

  @override
  String get profileAddresses => 'Addresses';

  @override
  String get profileSupport => 'Help and support';

  @override
  String get profileDelete => 'Delete account';

  @override
  String get signOut => 'Sign out';

  @override
  String appVersion(String version) {
    return 'Version $version';
  }

  @override
  String get editName => 'Edit name';

  @override
  String get noName => 'Add your name';

  @override
  String get signOutConfirm => 'Sign out of KitaabOnDemand?';

  @override
  String get addressesTitle => 'Addresses';

  @override
  String get addressesEmpty => 'Add an address to place orders.';

  @override
  String get addressFormNew => 'New address';

  @override
  String get addressFormEdit => 'Edit address';

  @override
  String get fieldRecipientName => 'Recipient name';

  @override
  String get fieldRecipientPhone => 'Recipient mobile number';

  @override
  String get fieldArea => 'Area or neighbourhood';

  @override
  String get fieldStreet => 'House, street and block';

  @override
  String get fieldLandmark => 'Nearest landmark';

  @override
  String get landmarkHint => 'For example: near Jamia Masjid';

  @override
  String get fieldLabel => 'Label, such as Home or Office';

  @override
  String get fieldDefault => 'Use as my default address';

  @override
  String get deleteAddressConfirm => 'Delete this address?';

  @override
  String get defaultBadge => 'Default';

  @override
  String get chooseCity => 'Choose a city';

  @override
  String get supportTitle => 'Help and support';

  @override
  String get supportCall => 'Call us';

  @override
  String get supportWhatsapp => 'WhatsApp';

  @override
  String get supportEmail => 'Email';

  @override
  String supportHours(String hours) {
    return 'Hours: $hours';
  }

  @override
  String get supportOpenFailed => 'Could not open this app.';

  @override
  String get deleteTitle => 'Delete account';

  @override
  String get deleteBody =>
      'This removes your profile, mobile number, addresses, notifications and uploaded files straight away. Payment records are kept without your personal details, as the law requires.';

  @override
  String get deleteInProgressNote =>
      'Orders that can still be cancelled will be cancelled. Orders already printing or on the way will be delivered first, and their delivery details are removed afterwards.';

  @override
  String get deleteTypeToConfirm => 'Type DELETE to confirm';

  @override
  String get deleteButton => 'Delete my account';

  @override
  String get deleteDone => 'Your account has been deleted.';
}
