import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_ur.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('ur'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'KitaabOnDemand'**
  String get appTitle;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get retry;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @confirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// No description provided for @continueLabel.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get continueLabel;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @edit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get edit;

  /// No description provided for @close.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;

  /// No description provided for @ok.
  ///
  /// In en, this message translates to:
  /// **'OK'**
  String get ok;

  /// No description provided for @errorGeneric.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong. Please try again.'**
  String get errorGeneric;

  /// No description provided for @errorOffline.
  ///
  /// In en, this message translates to:
  /// **'You are offline. Check your connection and try again.'**
  String get errorOffline;

  /// No description provided for @errorTimeout.
  ///
  /// In en, this message translates to:
  /// **'This is taking too long. Check your connection and try again.'**
  String get errorTimeout;

  /// No description provided for @errorSessionExpired.
  ///
  /// In en, this message translates to:
  /// **'Please sign in again.'**
  String get errorSessionExpired;

  /// No description provided for @errorRateLimited.
  ///
  /// In en, this message translates to:
  /// **'Too many attempts. Please wait a few minutes and try again.'**
  String get errorRateLimited;

  /// No description provided for @offlineBanner.
  ///
  /// In en, this message translates to:
  /// **'You are offline'**
  String get offlineBanner;

  /// No description provided for @optional.
  ///
  /// In en, this message translates to:
  /// **'Optional'**
  String get optional;

  /// No description provided for @fieldRequired.
  ///
  /// In en, this message translates to:
  /// **'This field is required'**
  String get fieldRequired;

  /// No description provided for @onboardingTitle1.
  ///
  /// In en, this message translates to:
  /// **'Find any book'**
  String get onboardingTitle1;

  /// No description provided for @onboardingBody1.
  ///
  /// In en, this message translates to:
  /// **'Tell us the book you need. We find it and send you a price.'**
  String get onboardingBody1;

  /// No description provided for @onboardingTitle2.
  ///
  /// In en, this message translates to:
  /// **'Print your PDF'**
  String get onboardingTitle2;

  /// No description provided for @onboardingBody2.
  ///
  /// In en, this message translates to:
  /// **'Upload a PDF, choose paper and binding, and we print it.'**
  String get onboardingBody2;

  /// No description provided for @onboardingTitle3.
  ///
  /// In en, this message translates to:
  /// **'Delivered to your door'**
  String get onboardingTitle3;

  /// No description provided for @onboardingBody3.
  ///
  /// In en, this message translates to:
  /// **'Pay cash on delivery or online, and track every step.'**
  String get onboardingBody3;

  /// No description provided for @onboardingSkip.
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get onboardingSkip;

  /// No description provided for @onboardingNext.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get onboardingNext;

  /// No description provided for @onboardingStart.
  ///
  /// In en, this message translates to:
  /// **'Get started'**
  String get onboardingStart;

  /// No description provided for @loginTitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get loginTitle;

  /// No description provided for @loginPhoneLabel.
  ///
  /// In en, this message translates to:
  /// **'Mobile number'**
  String get loginPhoneLabel;

  /// No description provided for @loginPhoneHint.
  ///
  /// In en, this message translates to:
  /// **'0300 1234567'**
  String get loginPhoneHint;

  /// No description provided for @loginSendCode.
  ///
  /// In en, this message translates to:
  /// **'Send code'**
  String get loginSendCode;

  /// No description provided for @loginWithGoogle.
  ///
  /// In en, this message translates to:
  /// **'Continue with Google'**
  String get loginWithGoogle;

  /// No description provided for @loginOr.
  ///
  /// In en, this message translates to:
  /// **'or'**
  String get loginOr;

  /// No description provided for @loginTermsNotice.
  ///
  /// In en, this message translates to:
  /// **'By continuing you agree to our Terms of Service and Privacy Policy.'**
  String get loginTermsNotice;

  /// No description provided for @phoneInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a Pakistani mobile number, for example 0300 1234567'**
  String get phoneInvalid;

  /// No description provided for @otpTitle.
  ///
  /// In en, this message translates to:
  /// **'Enter the code'**
  String get otpTitle;

  /// No description provided for @otpSentTo.
  ///
  /// In en, this message translates to:
  /// **'We sent a 6-digit code to {phone}'**
  String otpSentTo(String phone);

  /// No description provided for @otpCodeLabel.
  ///
  /// In en, this message translates to:
  /// **'6-digit code'**
  String get otpCodeLabel;

  /// No description provided for @otpResendIn.
  ///
  /// In en, this message translates to:
  /// **'Send a new code in {seconds}s'**
  String otpResendIn(int seconds);

  /// No description provided for @otpResend.
  ///
  /// In en, this message translates to:
  /// **'Send a new code'**
  String get otpResend;

  /// No description provided for @otpChangeNumber.
  ///
  /// In en, this message translates to:
  /// **'Change number'**
  String get otpChangeNumber;

  /// No description provided for @otpVerify.
  ///
  /// In en, this message translates to:
  /// **'Verify'**
  String get otpVerify;

  /// No description provided for @otpWrong.
  ///
  /// In en, this message translates to:
  /// **'Wrong code. {attempts} attempts left.'**
  String otpWrong(int attempts);

  /// No description provided for @otpWrongNoCount.
  ///
  /// In en, this message translates to:
  /// **'Wrong code. Please check and try again.'**
  String get otpWrongNoCount;

  /// No description provided for @otpExpired.
  ///
  /// In en, this message translates to:
  /// **'This code has expired. Send a new one.'**
  String get otpExpired;

  /// No description provided for @otpTooMany.
  ///
  /// In en, this message translates to:
  /// **'Too many attempts. Send a new code later.'**
  String get otpTooMany;

  /// No description provided for @googleSignInFailed.
  ///
  /// In en, this message translates to:
  /// **'Google sign-in did not finish. Try again or use your mobile number.'**
  String get googleSignInFailed;

  /// No description provided for @googleNotConfigured.
  ///
  /// In en, this message translates to:
  /// **'Google sign-in is not available in this build.'**
  String get googleNotConfigured;

  /// No description provided for @termsTitle.
  ///
  /// In en, this message translates to:
  /// **'Before you start'**
  String get termsTitle;

  /// No description provided for @termsSummary.
  ///
  /// In en, this message translates to:
  /// **'Please read and accept our Terms of Service and Privacy Policy. They explain how we handle your orders, files and personal details.'**
  String get termsSummary;

  /// No description provided for @termsAgree.
  ///
  /// In en, this message translates to:
  /// **'I agree to the Terms of Service and Privacy Policy'**
  String get termsAgree;

  /// No description provided for @termsOfService.
  ///
  /// In en, this message translates to:
  /// **'Terms of Service'**
  String get termsOfService;

  /// No description provided for @privacyPolicy.
  ///
  /// In en, this message translates to:
  /// **'Privacy Policy'**
  String get privacyPolicy;

  /// No description provided for @addPhoneTitle.
  ///
  /// In en, this message translates to:
  /// **'Add your mobile number'**
  String get addPhoneTitle;

  /// No description provided for @addPhoneBody.
  ///
  /// In en, this message translates to:
  /// **'We need a verified mobile number before your first order, for delivery updates and the courier.'**
  String get addPhoneBody;

  /// No description provided for @phoneInUse.
  ///
  /// In en, this message translates to:
  /// **'This number is already used by another account. Contact support for help.'**
  String get phoneInUse;

  /// No description provided for @navHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get navHome;

  /// No description provided for @navOrders.
  ///
  /// In en, this message translates to:
  /// **'Orders'**
  String get navOrders;

  /// No description provided for @navInbox.
  ///
  /// In en, this message translates to:
  /// **'Inbox'**
  String get navInbox;

  /// No description provided for @navProfile.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get navProfile;

  /// No description provided for @homeGreeting.
  ///
  /// In en, this message translates to:
  /// **'Hello, {name}'**
  String homeGreeting(String name);

  /// No description provided for @homeGreetingNoName.
  ///
  /// In en, this message translates to:
  /// **'Hello'**
  String get homeGreetingNoName;

  /// No description provided for @homeFindBookTitle.
  ///
  /// In en, this message translates to:
  /// **'Find a book'**
  String get homeFindBookTitle;

  /// No description provided for @homeFindBookBody.
  ///
  /// In en, this message translates to:
  /// **'We find it and send you a price'**
  String get homeFindBookBody;

  /// No description provided for @homePrintTitle.
  ///
  /// In en, this message translates to:
  /// **'Print my PDF'**
  String get homePrintTitle;

  /// No description provided for @homePrintBody.
  ///
  /// In en, this message translates to:
  /// **'Upload a file, we print and bind it'**
  String get homePrintBody;

  /// No description provided for @homeCalculator.
  ///
  /// In en, this message translates to:
  /// **'Price calculator'**
  String get homeCalculator;

  /// No description provided for @homeLatestOrder.
  ///
  /// In en, this message translates to:
  /// **'Your latest order'**
  String get homeLatestOrder;

  /// No description provided for @homeSeeAll.
  ///
  /// In en, this message translates to:
  /// **'See all orders'**
  String get homeSeeAll;

  /// No description provided for @notificationsTooltip.
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get notificationsTooltip;

  /// No description provided for @requestTitle.
  ///
  /// In en, this message translates to:
  /// **'Find a book'**
  String get requestTitle;

  /// No description provided for @fieldBookTitle.
  ///
  /// In en, this message translates to:
  /// **'Book title'**
  String get fieldBookTitle;

  /// No description provided for @fieldAuthor.
  ///
  /// In en, this message translates to:
  /// **'Author'**
  String get fieldAuthor;

  /// No description provided for @fieldIsbn.
  ///
  /// In en, this message translates to:
  /// **'ISBN'**
  String get fieldIsbn;

  /// No description provided for @fieldEdition.
  ///
  /// In en, this message translates to:
  /// **'Edition'**
  String get fieldEdition;

  /// No description provided for @fieldNotes.
  ///
  /// In en, this message translates to:
  /// **'Anything else we should know'**
  String get fieldNotes;

  /// No description provided for @fieldCopies.
  ///
  /// In en, this message translates to:
  /// **'Copies'**
  String get fieldCopies;

  /// No description provided for @fieldPreferredPaper.
  ///
  /// In en, this message translates to:
  /// **'Preferred paper'**
  String get fieldPreferredPaper;

  /// No description provided for @fieldPreferredBinding.
  ///
  /// In en, this message translates to:
  /// **'Preferred binding'**
  String get fieldPreferredBinding;

  /// No description provided for @noPreference.
  ///
  /// In en, this message translates to:
  /// **'No preference'**
  String get noPreference;

  /// No description provided for @fieldDeliveryAddress.
  ///
  /// In en, this message translates to:
  /// **'Delivery address'**
  String get fieldDeliveryAddress;

  /// No description provided for @addAddress.
  ///
  /// In en, this message translates to:
  /// **'Add address'**
  String get addAddress;

  /// No description provided for @changeAddress.
  ///
  /// In en, this message translates to:
  /// **'Change'**
  String get changeAddress;

  /// No description provided for @requestSubmit.
  ///
  /// In en, this message translates to:
  /// **'Send request'**
  String get requestSubmit;

  /// No description provided for @requestSubmitted.
  ///
  /// In en, this message translates to:
  /// **'We are looking for your book. We will send you a price soon.'**
  String get requestSubmitted;

  /// No description provided for @copiesRange.
  ///
  /// In en, this message translates to:
  /// **'Choose between 1 and {max} copies'**
  String copiesRange(int max);

  /// No description provided for @paperLocalWhite.
  ///
  /// In en, this message translates to:
  /// **'Local White'**
  String get paperLocalWhite;

  /// No description provided for @paperImportedYellow.
  ///
  /// In en, this message translates to:
  /// **'Imported Yellow'**
  String get paperImportedYellow;

  /// No description provided for @bindingSoftcover.
  ///
  /// In en, this message translates to:
  /// **'Softcover Paperback'**
  String get bindingSoftcover;

  /// No description provided for @bindingHardcover.
  ///
  /// In en, this message translates to:
  /// **'Premium Hardcover'**
  String get bindingHardcover;

  /// No description provided for @fieldPaper.
  ///
  /// In en, this message translates to:
  /// **'Paper'**
  String get fieldPaper;

  /// No description provided for @fieldBinding.
  ///
  /// In en, this message translates to:
  /// **'Binding'**
  String get fieldBinding;

  /// No description provided for @fieldPages.
  ///
  /// In en, this message translates to:
  /// **'Number of pages'**
  String get fieldPages;

  /// No description provided for @fieldCity.
  ///
  /// In en, this message translates to:
  /// **'Delivery city'**
  String get fieldCity;

  /// No description provided for @printTitle.
  ///
  /// In en, this message translates to:
  /// **'Print my PDF'**
  String get printTitle;

  /// No description provided for @printIntro.
  ///
  /// In en, this message translates to:
  /// **'Choose a PDF up to 150 MB. We check every file before printing.'**
  String get printIntro;

  /// No description provided for @printPickFile.
  ///
  /// In en, this message translates to:
  /// **'Choose PDF'**
  String get printPickFile;

  /// No description provided for @printChangeFile.
  ///
  /// In en, this message translates to:
  /// **'Choose another file'**
  String get printChangeFile;

  /// No description provided for @printPagesFound.
  ///
  /// In en, this message translates to:
  /// **'{pages} pages'**
  String printPagesFound(int pages);

  /// No description provided for @printPagesManual.
  ///
  /// In en, this message translates to:
  /// **'We could not read the page count. Enter it below and we will check it after upload.'**
  String get printPagesManual;

  /// No description provided for @printCopyright.
  ///
  /// In en, this message translates to:
  /// **'I own this file or have permission to print it.'**
  String get printCopyright;

  /// No description provided for @printTooLarge.
  ///
  /// In en, this message translates to:
  /// **'This file is larger than 150 MB. Please choose a smaller file.'**
  String get printTooLarge;

  /// No description provided for @printNotPdf.
  ///
  /// In en, this message translates to:
  /// **'Please choose a PDF file.'**
  String get printNotPdf;

  /// No description provided for @printPickFailed.
  ///
  /// In en, this message translates to:
  /// **'The file could not be opened. Please try another file.'**
  String get printPickFailed;

  /// No description provided for @pagesInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter the number of pages'**
  String get pagesInvalid;

  /// No description provided for @optionsTitle.
  ///
  /// In en, this message translates to:
  /// **'Print options'**
  String get optionsTitle;

  /// No description provided for @uploadAndContinue.
  ///
  /// In en, this message translates to:
  /// **'Upload and continue'**
  String get uploadAndContinue;

  /// No description provided for @pagesExceedBinding.
  ///
  /// In en, this message translates to:
  /// **'This binding allows up to {max} pages. Please choose another binding.'**
  String pagesExceedBinding(int max);

  /// No description provided for @cityNotServed.
  ///
  /// In en, this message translates to:
  /// **'We do not deliver to this city yet.'**
  String get cityNotServed;

  /// No description provided for @priceUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Prices could not be loaded.'**
  String get priceUnavailable;

  /// No description provided for @priceTitle.
  ///
  /// In en, this message translates to:
  /// **'Price'**
  String get priceTitle;

  /// No description provided for @pricePrinting.
  ///
  /// In en, this message translates to:
  /// **'Printing ({pages} pages × {copies})'**
  String pricePrinting(int pages, int copies);

  /// No description provided for @priceBinding.
  ///
  /// In en, this message translates to:
  /// **'Binding × {copies}'**
  String priceBinding(int copies);

  /// No description provided for @priceSourcing.
  ///
  /// In en, this message translates to:
  /// **'Finding the book'**
  String get priceSourcing;

  /// No description provided for @priceRounding.
  ///
  /// In en, this message translates to:
  /// **'Rounding'**
  String get priceRounding;

  /// No description provided for @priceDelivery.
  ///
  /// In en, this message translates to:
  /// **'Delivery'**
  String get priceDelivery;

  /// No description provided for @priceCodFee.
  ///
  /// In en, this message translates to:
  /// **'Cash on delivery fee'**
  String get priceCodFee;

  /// No description provided for @priceTotal.
  ///
  /// In en, this message translates to:
  /// **'Total'**
  String get priceTotal;

  /// No description provided for @priceGoods.
  ///
  /// In en, this message translates to:
  /// **'Book and printing'**
  String get priceGoods;

  /// No description provided for @uploadTitle.
  ///
  /// In en, this message translates to:
  /// **'Uploading your file'**
  String get uploadTitle;

  /// No description provided for @uploadProgress.
  ///
  /// In en, this message translates to:
  /// **'{sent} of {total}'**
  String uploadProgress(String sent, String total);

  /// No description provided for @uploadPaused.
  ///
  /// In en, this message translates to:
  /// **'Paused'**
  String get uploadPaused;

  /// No description provided for @uploadWaitingNetwork.
  ///
  /// In en, this message translates to:
  /// **'Waiting for connection. Your upload will continue.'**
  String get uploadWaitingNetwork;

  /// No description provided for @uploadChecking.
  ///
  /// In en, this message translates to:
  /// **'Checking your file…'**
  String get uploadChecking;

  /// No description provided for @uploadReady.
  ///
  /// In en, this message translates to:
  /// **'Your file is ready'**
  String get uploadReady;

  /// No description provided for @uploadPause.
  ///
  /// In en, this message translates to:
  /// **'Pause'**
  String get uploadPause;

  /// No description provided for @uploadResume.
  ///
  /// In en, this message translates to:
  /// **'Resume'**
  String get uploadResume;

  /// No description provided for @uploadStarting.
  ///
  /// In en, this message translates to:
  /// **'Preparing upload…'**
  String get uploadStarting;

  /// No description provided for @uploadRejectedTitle.
  ///
  /// In en, this message translates to:
  /// **'We cannot print this file'**
  String get uploadRejectedTitle;

  /// No description provided for @rejectCorrupt.
  ///
  /// In en, this message translates to:
  /// **'The file is damaged or is not a real PDF.'**
  String get rejectCorrupt;

  /// No description provided for @rejectEncrypted.
  ///
  /// In en, this message translates to:
  /// **'The file is password-protected. Remove the password and try again.'**
  String get rejectEncrypted;

  /// No description provided for @rejectNoPages.
  ///
  /// In en, this message translates to:
  /// **'The file has no pages.'**
  String get rejectNoPages;

  /// No description provided for @rejectActiveContent.
  ///
  /// In en, this message translates to:
  /// **'The file contains scripts or attachments, which we cannot accept.'**
  String get rejectActiveContent;

  /// No description provided for @rejectTooLarge.
  ///
  /// In en, this message translates to:
  /// **'The file is larger than 150 MB.'**
  String get rejectTooLarge;

  /// No description provided for @rejectMalware.
  ///
  /// In en, this message translates to:
  /// **'The file failed our safety check.'**
  String get rejectMalware;

  /// No description provided for @rejectGeneric.
  ///
  /// In en, this message translates to:
  /// **'The file could not be checked. Please try again.'**
  String get rejectGeneric;

  /// No description provided for @pageMismatchTitle.
  ///
  /// In en, this message translates to:
  /// **'Page count updated'**
  String get pageMismatchTitle;

  /// No description provided for @pageMismatchBody.
  ///
  /// In en, this message translates to:
  /// **'Your file has {pages} pages, not {localPages}. The new total is {price}.'**
  String pageMismatchBody(int pages, int localPages, String price);

  /// No description provided for @leaveUploadTitle.
  ///
  /// In en, this message translates to:
  /// **'Leave this screen?'**
  String get leaveUploadTitle;

  /// No description provided for @leaveUploadBody.
  ///
  /// In en, this message translates to:
  /// **'Your upload will keep going and you can come back to it.'**
  String get leaveUploadBody;

  /// No description provided for @leave.
  ///
  /// In en, this message translates to:
  /// **'Leave'**
  String get leave;

  /// No description provided for @stay.
  ///
  /// In en, this message translates to:
  /// **'Stay'**
  String get stay;

  /// No description provided for @resumeUploadBanner.
  ///
  /// In en, this message translates to:
  /// **'You have an unfinished upload: {file}'**
  String resumeUploadBanner(String file);

  /// No description provided for @resumeUploadAction.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get resumeUploadAction;

  /// No description provided for @checkoutTitle.
  ///
  /// In en, this message translates to:
  /// **'Checkout'**
  String get checkoutTitle;

  /// No description provided for @orderSummary.
  ///
  /// In en, this message translates to:
  /// **'Order summary'**
  String get orderSummary;

  /// No description provided for @paymentMethodTitle.
  ///
  /// In en, this message translates to:
  /// **'Payment method'**
  String get paymentMethodTitle;

  /// No description provided for @payCod.
  ///
  /// In en, this message translates to:
  /// **'Cash on delivery'**
  String get payCod;

  /// No description provided for @payEasypaisa.
  ///
  /// In en, this message translates to:
  /// **'Easypaisa'**
  String get payEasypaisa;

  /// No description provided for @payJazzcash.
  ///
  /// In en, this message translates to:
  /// **'JazzCash'**
  String get payJazzcash;

  /// No description provided for @payCard.
  ///
  /// In en, this message translates to:
  /// **'Debit or credit card'**
  String get payCard;

  /// No description provided for @codNotAllowed.
  ///
  /// In en, this message translates to:
  /// **'Cash on delivery is not available for orders above {amount}.'**
  String codNotAllowed(String amount);

  /// No description provided for @placeOrder.
  ///
  /// In en, this message translates to:
  /// **'Place order'**
  String get placeOrder;

  /// No description provided for @priceChangedTitle.
  ///
  /// In en, this message translates to:
  /// **'Price updated'**
  String get priceChangedTitle;

  /// No description provided for @priceChangedBody.
  ///
  /// In en, this message translates to:
  /// **'The total is now {price}. Do you want to continue?'**
  String priceChangedBody(String price);

  /// No description provided for @noAddressYet.
  ///
  /// In en, this message translates to:
  /// **'Add a delivery address to continue.'**
  String get noAddressYet;

  /// No description provided for @paymentChecking.
  ///
  /// In en, this message translates to:
  /// **'Checking your payment…'**
  String get paymentChecking;

  /// No description provided for @paymentSuccess.
  ///
  /// In en, this message translates to:
  /// **'Payment received'**
  String get paymentSuccess;

  /// No description provided for @paymentFailed.
  ///
  /// In en, this message translates to:
  /// **'The payment did not go through.'**
  String get paymentFailed;

  /// No description provided for @paymentChooseOther.
  ///
  /// In en, this message translates to:
  /// **'Choose another method'**
  String get paymentChooseOther;

  /// No description provided for @payNow.
  ///
  /// In en, this message translates to:
  /// **'Pay now'**
  String get payNow;

  /// No description provided for @awaitingPayment.
  ///
  /// In en, this message translates to:
  /// **'Awaiting payment'**
  String get awaitingPayment;

  /// No description provided for @openPaymentPage.
  ///
  /// In en, this message translates to:
  /// **'Open payment page'**
  String get openPaymentPage;

  /// No description provided for @paymentPageNotOpened.
  ///
  /// In en, this message translates to:
  /// **'The payment page could not be opened.'**
  String get paymentPageNotOpened;

  /// No description provided for @calculatorTitle.
  ///
  /// In en, this message translates to:
  /// **'Price calculator'**
  String get calculatorTitle;

  /// No description provided for @calculatorHint.
  ///
  /// In en, this message translates to:
  /// **'Prices are estimates. We confirm the page count when you upload your file.'**
  String get calculatorHint;

  /// No description provided for @ordersTitle.
  ///
  /// In en, this message translates to:
  /// **'My orders'**
  String get ordersTitle;

  /// No description provided for @ordersActive.
  ///
  /// In en, this message translates to:
  /// **'Active'**
  String get ordersActive;

  /// No description provided for @ordersPast.
  ///
  /// In en, this message translates to:
  /// **'Past'**
  String get ordersPast;

  /// No description provided for @ordersEmpty.
  ///
  /// In en, this message translates to:
  /// **'No orders yet'**
  String get ordersEmpty;

  /// No description provided for @ordersEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Find a book or print your PDF to get started.'**
  String get ordersEmptyBody;

  /// No description provided for @orderCode.
  ///
  /// In en, this message translates to:
  /// **'Order {code}'**
  String orderCode(String code);

  /// No description provided for @needsAction.
  ///
  /// In en, this message translates to:
  /// **'Action needed'**
  String get needsAction;

  /// No description provided for @loadMore.
  ///
  /// In en, this message translates to:
  /// **'Load more'**
  String get loadMore;

  /// No description provided for @statusPendingPayment.
  ///
  /// In en, this message translates to:
  /// **'Awaiting payment'**
  String get statusPendingPayment;

  /// No description provided for @statusPlaced.
  ///
  /// In en, this message translates to:
  /// **'Placed'**
  String get statusPlaced;

  /// No description provided for @statusVerifying.
  ///
  /// In en, this message translates to:
  /// **'Being checked'**
  String get statusVerifying;

  /// No description provided for @statusAssigned.
  ///
  /// In en, this message translates to:
  /// **'Sent to printer'**
  String get statusAssigned;

  /// No description provided for @statusInPrint.
  ///
  /// In en, this message translates to:
  /// **'Printing'**
  String get statusInPrint;

  /// No description provided for @statusReadyForDispatch.
  ///
  /// In en, this message translates to:
  /// **'Ready to ship'**
  String get statusReadyForDispatch;

  /// No description provided for @statusDispatched.
  ///
  /// In en, this message translates to:
  /// **'Out for delivery'**
  String get statusDispatched;

  /// No description provided for @statusDelivered.
  ///
  /// In en, this message translates to:
  /// **'Delivered'**
  String get statusDelivered;

  /// No description provided for @statusCompleted.
  ///
  /// In en, this message translates to:
  /// **'Completed'**
  String get statusCompleted;

  /// No description provided for @statusRejected.
  ///
  /// In en, this message translates to:
  /// **'Not accepted'**
  String get statusRejected;

  /// No description provided for @statusCancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get statusCancelled;

  /// No description provided for @statusDeliveryFailed.
  ///
  /// In en, this message translates to:
  /// **'Delivery failed'**
  String get statusDeliveryFailed;

  /// No description provided for @statusRequested.
  ///
  /// In en, this message translates to:
  /// **'Looking for book'**
  String get statusRequested;

  /// No description provided for @statusQuoted.
  ///
  /// In en, this message translates to:
  /// **'Quote ready'**
  String get statusQuoted;

  /// No description provided for @statusAccepted.
  ///
  /// In en, this message translates to:
  /// **'Quote accepted'**
  String get statusAccepted;

  /// No description provided for @statusSourcing.
  ///
  /// In en, this message translates to:
  /// **'Getting your book'**
  String get statusSourcing;

  /// No description provided for @statusQuoteExpired.
  ///
  /// In en, this message translates to:
  /// **'Quote expired'**
  String get statusQuoteExpired;

  /// No description provided for @statusDeclined.
  ///
  /// In en, this message translates to:
  /// **'Declined'**
  String get statusDeclined;

  /// No description provided for @statusUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Not available'**
  String get statusUnavailable;

  /// No description provided for @stepPlaced.
  ///
  /// In en, this message translates to:
  /// **'Order placed'**
  String get stepPlaced;

  /// No description provided for @stepVerifying.
  ///
  /// In en, this message translates to:
  /// **'Verifying'**
  String get stepVerifying;

  /// No description provided for @stepSourcing.
  ///
  /// In en, this message translates to:
  /// **'Sourcing'**
  String get stepSourcing;

  /// No description provided for @stepPrinting.
  ///
  /// In en, this message translates to:
  /// **'Printing'**
  String get stepPrinting;

  /// No description provided for @stepOutForDelivery.
  ///
  /// In en, this message translates to:
  /// **'Out for delivery'**
  String get stepOutForDelivery;

  /// No description provided for @stepCompleted.
  ///
  /// In en, this message translates to:
  /// **'Completed'**
  String get stepCompleted;

  /// No description provided for @exitRejected.
  ///
  /// In en, this message translates to:
  /// **'Your file was not accepted'**
  String get exitRejected;

  /// No description provided for @exitCancelled.
  ///
  /// In en, this message translates to:
  /// **'This order was cancelled'**
  String get exitCancelled;

  /// No description provided for @exitQuoteExpired.
  ///
  /// In en, this message translates to:
  /// **'This quote has expired'**
  String get exitQuoteExpired;

  /// No description provided for @exitDeclined.
  ///
  /// In en, this message translates to:
  /// **'You declined this quote'**
  String get exitDeclined;

  /// No description provided for @exitUnavailable.
  ///
  /// In en, this message translates to:
  /// **'We could not find this book'**
  String get exitUnavailable;

  /// No description provided for @exitDeliveryFailed.
  ///
  /// In en, this message translates to:
  /// **'The delivery did not succeed'**
  String get exitDeliveryFailed;

  /// No description provided for @exitReason.
  ///
  /// In en, this message translates to:
  /// **'Reason: {reason}'**
  String exitReason(String reason);

  /// No description provided for @requestAgain.
  ///
  /// In en, this message translates to:
  /// **'Request again'**
  String get requestAgain;

  /// No description provided for @orderDetailTitle.
  ///
  /// In en, this message translates to:
  /// **'Order details'**
  String get orderDetailTitle;

  /// No description provided for @quoteTitle.
  ///
  /// In en, this message translates to:
  /// **'Your quote'**
  String get quoteTitle;

  /// No description provided for @quoteValidUntil.
  ///
  /// In en, this message translates to:
  /// **'Valid until {time}'**
  String quoteValidUntil(String time);

  /// No description provided for @quoteFor.
  ///
  /// In en, this message translates to:
  /// **'{pages} pages, {paper}, {binding}, {copies} copies'**
  String quoteFor(int pages, String paper, String binding, int copies);

  /// No description provided for @quoteTotalDigital.
  ///
  /// In en, this message translates to:
  /// **'Pay online: {amount}'**
  String quoteTotalDigital(String amount);

  /// No description provided for @quoteTotalCod.
  ///
  /// In en, this message translates to:
  /// **'Cash on delivery: {amount}'**
  String quoteTotalCod(String amount);

  /// No description provided for @quoteAccept.
  ///
  /// In en, this message translates to:
  /// **'Accept and order'**
  String get quoteAccept;

  /// No description provided for @quoteDecline.
  ///
  /// In en, this message translates to:
  /// **'Decline'**
  String get quoteDecline;

  /// No description provided for @quoteDeclineConfirm.
  ///
  /// In en, this message translates to:
  /// **'Decline this quote?'**
  String get quoteDeclineConfirm;

  /// No description provided for @quoteChoosePayment.
  ///
  /// In en, this message translates to:
  /// **'How would you like to pay?'**
  String get quoteChoosePayment;

  /// No description provided for @trackingTitle.
  ///
  /// In en, this message translates to:
  /// **'Tracking'**
  String get trackingTitle;

  /// No description provided for @trackingCourier.
  ///
  /// In en, this message translates to:
  /// **'Courier'**
  String get trackingCourier;

  /// No description provided for @trackingCn.
  ///
  /// In en, this message translates to:
  /// **'Tracking number'**
  String get trackingCn;

  /// No description provided for @trackingOpen.
  ///
  /// In en, this message translates to:
  /// **'Track parcel'**
  String get trackingOpen;

  /// No description provided for @deliveryAddressTitle.
  ///
  /// In en, this message translates to:
  /// **'Delivery address'**
  String get deliveryAddressTitle;

  /// No description provided for @landmarkPrefix.
  ///
  /// In en, this message translates to:
  /// **'Near: {landmark}'**
  String landmarkPrefix(String landmark);

  /// No description provided for @paymentTitle.
  ///
  /// In en, this message translates to:
  /// **'Payment'**
  String get paymentTitle;

  /// No description provided for @paymentPending.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get paymentPending;

  /// No description provided for @paymentPaid.
  ///
  /// In en, this message translates to:
  /// **'Paid'**
  String get paymentPaid;

  /// No description provided for @paymentFailedStatus.
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get paymentFailedStatus;

  /// No description provided for @paymentRefunded.
  ///
  /// In en, this message translates to:
  /// **'Refunded'**
  String get paymentRefunded;

  /// No description provided for @cancelOrder.
  ///
  /// In en, this message translates to:
  /// **'Cancel order'**
  String get cancelOrder;

  /// No description provided for @cancelOrderConfirm.
  ///
  /// In en, this message translates to:
  /// **'Cancel this order? This cannot be undone.'**
  String get cancelOrderConfirm;

  /// No description provided for @fileTitle.
  ///
  /// In en, this message translates to:
  /// **'File'**
  String get fileTitle;

  /// No description provided for @bookSection.
  ///
  /// In en, this message translates to:
  /// **'Book'**
  String get bookSection;

  /// No description provided for @optionsSection.
  ///
  /// In en, this message translates to:
  /// **'Options'**
  String get optionsSection;

  /// No description provided for @byAuthor.
  ///
  /// In en, this message translates to:
  /// **'by {author}'**
  String byAuthor(String author);

  /// No description provided for @inboxTitle.
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get inboxTitle;

  /// No description provided for @inboxEmpty.
  ///
  /// In en, this message translates to:
  /// **'No notifications yet'**
  String get inboxEmpty;

  /// No description provided for @markAllRead.
  ///
  /// In en, this message translates to:
  /// **'Mark all read'**
  String get markAllRead;

  /// No description provided for @profileTitle.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profileTitle;

  /// No description provided for @profileName.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get profileName;

  /// No description provided for @profilePhone.
  ///
  /// In en, this message translates to:
  /// **'Mobile number'**
  String get profilePhone;

  /// No description provided for @profileAddresses.
  ///
  /// In en, this message translates to:
  /// **'Addresses'**
  String get profileAddresses;

  /// No description provided for @profileSupport.
  ///
  /// In en, this message translates to:
  /// **'Help and support'**
  String get profileSupport;

  /// No description provided for @profileDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete account'**
  String get profileDelete;

  /// No description provided for @signOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get signOut;

  /// No description provided for @appVersion.
  ///
  /// In en, this message translates to:
  /// **'Version {version}'**
  String appVersion(String version);

  /// No description provided for @editName.
  ///
  /// In en, this message translates to:
  /// **'Edit name'**
  String get editName;

  /// No description provided for @noName.
  ///
  /// In en, this message translates to:
  /// **'Add your name'**
  String get noName;

  /// No description provided for @signOutConfirm.
  ///
  /// In en, this message translates to:
  /// **'Sign out of KitaabOnDemand?'**
  String get signOutConfirm;

  /// No description provided for @addressesTitle.
  ///
  /// In en, this message translates to:
  /// **'Addresses'**
  String get addressesTitle;

  /// No description provided for @addressesEmpty.
  ///
  /// In en, this message translates to:
  /// **'Add an address to place orders.'**
  String get addressesEmpty;

  /// No description provided for @addressFormNew.
  ///
  /// In en, this message translates to:
  /// **'New address'**
  String get addressFormNew;

  /// No description provided for @addressFormEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit address'**
  String get addressFormEdit;

  /// No description provided for @fieldRecipientName.
  ///
  /// In en, this message translates to:
  /// **'Recipient name'**
  String get fieldRecipientName;

  /// No description provided for @fieldRecipientPhone.
  ///
  /// In en, this message translates to:
  /// **'Recipient mobile number'**
  String get fieldRecipientPhone;

  /// No description provided for @fieldArea.
  ///
  /// In en, this message translates to:
  /// **'Area or neighbourhood'**
  String get fieldArea;

  /// No description provided for @fieldStreet.
  ///
  /// In en, this message translates to:
  /// **'House, street and block'**
  String get fieldStreet;

  /// No description provided for @fieldLandmark.
  ///
  /// In en, this message translates to:
  /// **'Nearest landmark'**
  String get fieldLandmark;

  /// No description provided for @landmarkHint.
  ///
  /// In en, this message translates to:
  /// **'For example: near Jamia Masjid'**
  String get landmarkHint;

  /// No description provided for @fieldLabel.
  ///
  /// In en, this message translates to:
  /// **'Label, such as Home or Office'**
  String get fieldLabel;

  /// No description provided for @fieldDefault.
  ///
  /// In en, this message translates to:
  /// **'Use as my default address'**
  String get fieldDefault;

  /// No description provided for @deleteAddressConfirm.
  ///
  /// In en, this message translates to:
  /// **'Delete this address?'**
  String get deleteAddressConfirm;

  /// No description provided for @defaultBadge.
  ///
  /// In en, this message translates to:
  /// **'Default'**
  String get defaultBadge;

  /// No description provided for @chooseCity.
  ///
  /// In en, this message translates to:
  /// **'Choose a city'**
  String get chooseCity;

  /// No description provided for @supportTitle.
  ///
  /// In en, this message translates to:
  /// **'Help and support'**
  String get supportTitle;

  /// No description provided for @supportCall.
  ///
  /// In en, this message translates to:
  /// **'Call us'**
  String get supportCall;

  /// No description provided for @supportWhatsapp.
  ///
  /// In en, this message translates to:
  /// **'WhatsApp'**
  String get supportWhatsapp;

  /// No description provided for @supportEmail.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get supportEmail;

  /// No description provided for @supportHours.
  ///
  /// In en, this message translates to:
  /// **'Hours: {hours}'**
  String supportHours(String hours);

  /// No description provided for @supportOpenFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not open this app.'**
  String get supportOpenFailed;

  /// No description provided for @deleteTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete account'**
  String get deleteTitle;

  /// No description provided for @deleteBody.
  ///
  /// In en, this message translates to:
  /// **'This removes your profile, mobile number, addresses, notifications and uploaded files straight away. Payment records are kept without your personal details, as the law requires.'**
  String get deleteBody;

  /// No description provided for @deleteInProgressNote.
  ///
  /// In en, this message translates to:
  /// **'Orders that can still be cancelled will be cancelled. Orders already printing or on the way will be delivered first, and their delivery details are removed afterwards.'**
  String get deleteInProgressNote;

  /// No description provided for @deleteTypeToConfirm.
  ///
  /// In en, this message translates to:
  /// **'Type DELETE to confirm'**
  String get deleteTypeToConfirm;

  /// No description provided for @deleteButton.
  ///
  /// In en, this message translates to:
  /// **'Delete my account'**
  String get deleteButton;

  /// No description provided for @deleteDone.
  ///
  /// In en, this message translates to:
  /// **'Your account has been deleted.'**
  String get deleteDone;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'ur'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'ur':
      return AppLocalizationsUr();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
