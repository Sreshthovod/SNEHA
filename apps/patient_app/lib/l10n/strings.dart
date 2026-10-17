/// Small string-table localization layer.
///
/// English is complete. Hindi, Assamese and Bengali tables cover core
/// navigation only and are DRAFTS: they must be reviewed by native speakers
/// (ideally with older users) before release. Missing keys fall back to
/// English. Other supported languages currently show English and the language
/// screen says so.
library;

class LanguageOption {
  const LanguageOption(this.code, this.nativeName, this.englishName);

  final String code;
  final String nativeName;
  final String englishName;
}

/// Codes match the backend `Language` enum.
const supportedLanguages = <LanguageOption>[
  LanguageOption('as', 'অসমীয়া', 'Assamese'),
  LanguageOption('bn', 'বাংলা', 'Bengali'),
  LanguageOption('brx', "बर'", 'Bodo'),
  LanguageOption('en', 'English', 'English'),
  LanguageOption('grt', 'A·chik', 'Garo'),
  LanguageOption('hi', 'हिन्दी', 'Hindi'),
  LanguageOption('kha', 'Ka Ktien Khasi', 'Khasi'),
  LanguageOption('mni', 'Meiteilon', 'Manipuri'),
  LanguageOption('lus', 'Mizo ṭawng', 'Mizo'),
  LanguageOption('nag', 'Nagamese', 'Nagamese'),
  LanguageOption('ne', 'नेपाली', 'Nepali'),
];

enum TranslationStatus { complete, draft, englishFallback }

TranslationStatus translationStatus(String code) => switch (code) {
  'en' => TranslationStatus.complete,
  'hi' || 'as' || 'bn' => TranslationStatus.draft,
  _ => TranslationStatus.englishFallback,
};

class AppStrings {
  AppStrings(this.languageCode);

  final String languageCode;

  /// Look up [key], substituting `{name}` style [args]. Falls back to English.
  String t(String key, [Map<String, Object> args = const {}]) {
    var value = _tables[languageCode]?[key] ?? english[key];
    assert(value != null, 'Missing English string for "$key"');
    value ??= key;
    args.forEach((k, v) => value = value!.replaceAll('{$k}', '$v'));
    return value!;
  }

  /// Like [t] with a `{count}`, using the `<key>_one` form for a count of 1
  /// when the same language table provides it (so a translated sentence is
  /// never swapped for an English singular).
  String tCount(String key, int count, [Map<String, Object> args = const {}]) {
    final own = _tables[languageCode];
    final table = own != null && own.containsKey(key) ? own : english;
    final one = '${key}_one';
    final useOne = count == 1 && table.containsKey(one);
    return t(useOne ? one : key, {...args, 'count': count});
  }

  static const english = <String, String>{
    'app_name': 'SNEHA',
    'common_continue': 'Continue',
    'common_back': 'Back',
    'common_cancel': 'Cancel',
    'common_done': 'Done',
    'common_retry': 'Try again',
    'common_loading': 'Loading…',
    'common_keep_going': 'Keep going',
    'common_yes_stop': 'Yes, stop',
    'error_generic': 'Something went wrong. Please try again.',
    'startup_error':
        'SNEHA could not start. Please close the app and open it again.',
    // Welcome / onboarding
    'welcome_title': 'Namaste',
    'welcome_body':
        "SNEHA offers gentle games and your family's memories, at your own pace.",
    'welcome_point_offline': 'Works without the internet.',
    'welcome_point_family': 'Your family chooses the photos and memories.',
    'welcome_point_pace': 'There is no hurry. You can stop at any time.',
    'welcome_start': "Let's begin",
    // Language
    'language_title': 'Choose your language',
    'language_body': 'You can change this later in Settings.',
    'language_draft_note': 'This translation is a draft and is being checked.',
    'language_english_fallback':
        'Screens in this language are not ready yet. English will be shown.',
    // Profiles and pairing
    'profiles_title': 'Who is using SNEHA?',
    'profiles_empty_title': 'No one is set up yet',
    'profiles_empty_body':
        'Ask your caregiver for a pairing code from the SNEHA dashboard.',
    'profiles_add': 'Add a person',
    'profiles_needs_repair': 'Needs a new pairing code to share progress',
    'pair_title': 'Add a person',
    'pair_body':
        'Enter the 8-letter code your caregiver gives you. This needs the internet once.',
    'pair_code_label': 'Pairing code',
    'pair_code_hint': 'ABCD-2345',
    'pair_device_label': 'Name for this phone',
    'pair_device_default': 'Patient phone',
    'pair_submit': 'Connect',
    'pair_working': 'Connecting…',
    'pair_error_format': 'Please enter all 8 letters and numbers of the code.',
    'pair_error_device': 'Please enter a name for this phone.',
    'pair_error_invalid':
        'This code is not valid or has expired. Ask your caregiver for a new one.',
    'pair_error_offline':
        'Cannot connect right now. Pairing needs the internet. Please try again later.',
    'pair_error_rate': 'Too many tries. Please wait a minute and try again.',
    'pair_error_other': 'Something went wrong. Please try again.',
    // Home
    'home_greeting': 'Namaste, {name}',
    'home_play': 'Play an activity',
    'home_memories': 'Look at memories',
    'home_talk': 'Talk with the helper',
    'home_settings': 'Settings',
    'home_sync': 'Sharing and offline',
    'home_privacy': 'Privacy',
    'home_switch': 'Change person',
    'home_today': 'Today',
    'home_today_empty': 'Nothing planned for today.',
    'home_needs_repair':
        'This phone needs a new pairing code to share progress. Activities still work.',
    // Connection
    'conn_checking': 'Checking connection…',
    'conn_checking_body': 'You can keep using SNEHA while we check.',
    'conn_online': 'Connected',
    'conn_online_body':
        'Activities work on this phone. Progress can be shared with your family.',
    'conn_offline': 'Working on this phone',
    'conn_offline_body':
        'No internet needed. Activities still work and are saved on this phone.',
    // Activity selection
    'activities_title': 'Choose an activity',
    'activities_empty_title': 'Activities are not on this phone yet',
    'activities_empty_body':
        'Connect to the internet once and tap "Sync now" in Sharing and offline.',
    'activities_coming_soon': 'Coming soon',
    'activities_needs_memories': 'Your family can add photos to use this.',
    'activities_start': 'Start {name}',
    // Runner
    'runner_round': '{current} of {total}',
    'runner_pause': 'Pause',
    'runner_resume': 'Carry on',
    'runner_hint': 'Hint',
    'runner_skip': 'Skip',
    'runner_stop': 'Stop',
    'runner_paused_title': 'Paused',
    'runner_paused_body': 'Take your time. Tap Carry on when you are ready.',
    'runner_error_body': 'What you did so far is still saved on this phone.',
    'runner_stop_title': 'Stop this activity?',
    'runner_stop_body': "That's fine. What you did so far is saved.",
    'runner_correct': "Yes, that's right!",
    'runner_try_again': 'Not quite. Have another look.',
    'runner_not_this_one': 'Not this one',
    'runner_saving': 'Saving…',
    // Games
    'game_photo_recall_q': 'What is this photo of?',
    'game_faces_q': 'Which photo shows {name}?',
    'game_object_q': 'What is this?',
    'game_sort_q': '{item}: where does it belong?',
    'game_photo_option': 'Photo {number}',
    'game_memory_photo': 'Memory photo',
    'game_sequence_today': "Today's routine",
    'game_sequence_q': '{task}: tap the steps in order.',
    'game_sequence_done': 'Steps so far:',
    'game_pairs_q': 'Find the matching pairs. Tap two cards.',
    'game_pairs_found': 'Pairs found: {found} of {total}',
    'game_card_hidden': 'Hidden card {number}',
    'hint_removed': 'One answer has been taken away.',
    'hint_sequence': 'The next step is highlighted.',
    'hint_pairs': 'A matching pair is shown.',
    'hint_year': 'This memory is from around {year}.',
    // Result
    'result_title_done': 'Well done!',
    'result_title_stopped': 'Thank you for playing',
    'result_body_done':
        'You took part in {name}. Every time you play is good practice.',
    'result_body_stopped': 'You can come back any time.',
    'result_rounds': 'You played {count} rounds.',
    'result_rounds_one': 'You played {count} round.',
    'result_time': 'Time spent: {minutes} min',
    'result_hints': 'Hints used: {count}',
    'result_again': 'Play again',
    'result_other': 'Choose another activity',
    'result_home': 'Go home',
    // Memories (story time)
    'story_title': 'Memories',
    'story_prompt_1': 'Who or what is in this photo?',
    'story_prompt_2': 'Where was this? What do you remember?',
    'story_prompt_3': 'Would you like to tell someone about it?',
    'story_next': 'Next memory',
    'story_back': 'Previous memory',
    'story_position': 'Memory {current} of {total}',
    'story_finish': 'Finish',
    'story_year': 'Around {year}',
    'memory_empty_title': 'No memories yet',
    'memory_empty_body':
        'Ask your family to add photos and memories in SNEHA. They will appear here.',
    // Conversation
    'talk_title': 'Talk with SNEHA',
    'talk_label':
        'This helper works on this phone. It understands a few simple questions only.',
    'talk_input': 'Type a message',
    'talk_send': 'Send',
    'talk_voice_disabled': 'Voice is not available yet',
    'talk_privacy': 'Your words are not saved.',
    'talk_quick_hello': 'Hello',
    'talk_quick_time': 'What time is it?',
    'talk_quick_date': 'What day is it?',
    'talk_quick_today': 'What do I do today?',
    'talk_quick_memory': 'Show me a memory',
    'talk_quick_family': 'I want my family',
    'talk_quick_unwell': "I don't feel well",
    'talk_reply_greeting': 'Namaste, {name}. It is nice to talk with you.',
    'talk_reply_time': 'It is {time} now.',
    'talk_reply_date': 'Today is {date}.',
    'talk_reply_today_none':
        'Nothing is planned for today. You could play an activity if you like.',
    'talk_reply_today': 'Today: {items}.',
    'talk_reply_memory': 'Here is a memory: {title}. Do you remember it?',
    'talk_reply_memory_none':
        'There are no memories on this phone yet. Your family can add some.',
    'talk_reply_family':
        'Please ask someone near you to call your family. You can show them this phone.',
    'talk_reply_unwell':
        "I'm sorry you don't feel well. Please tell someone near you or call your family. In an emergency, call 112.",
    // Mirror the server's reviewed English templates (conversation/templates.py).
    'talk_reply_stop':
        'All right, we can stop now. Thank you for spending time with me.',
    'talk_reply_tired':
        "Let's take a little rest. We can do something gentle later.",
    'talk_reply_scared':
        "I'm sorry you feel this way. Please call a family member now. If it is an emergency, call 112.",
    'talk_reply_thanks': "You're welcome.",
    'talk_reply_unknown':
        "I'm a simple helper and didn't understand. Try one of the buttons below.",
    'talk_label_online':
        'When the phone is online, SNEHA helps understand you. It only uses memories your family has approved.',
    'talk_source_online': 'Answered with help from SNEHA',
    'talk_source_offline': 'Answered on this phone (simple helper)',
    'talk_offline_note':
        'No connection right now, so the simple helper on this phone answered.',
    'talk_thinking': 'Thinking…',
    'talk_memories_heading': 'Memories your family added',
    'talk_suggest_heading': 'Would you like to try this?',
    'talk_suggest_start': 'Start',
    'talk_suggest_rest':
        'A short rest may feel good. Here is something easy for later.',
    'talk_candidate_heading': 'Something new to remember?',
    'talk_candidate_body':
        'This is not saved yet. Your family can check it and add it.',
    'talk_candidate_save': 'Save for my family to check',
    'talk_candidate_saved': 'Sent. Your family will check this first.',
    'talk_candidate_failed': 'Could not send this now. Please try again later.',
    'talk_you': 'You',
    'talk_helper': 'Helper',
    // Settings
    'settings_title': 'Settings',
    'settings_language': 'Language',
    'settings_text_size': 'Text size',
    'settings_text_normal': 'Normal',
    'settings_text_large': 'Large',
    'settings_text_xl': 'Extra large',
    'settings_preview': 'This is how text will look.',
    'settings_display_title': 'Screen and sound',
    'settings_contrast': 'High contrast',
    'settings_contrast_body': 'Stronger colours and borders.',
    'settings_motion': 'Reduce motion',
    'settings_motion_body': 'Turn off movement and animations.',
    'settings_motion_system': 'Your phone already asks for less motion.',
    // Sync
    'sync_title': 'Sharing and offline',
    'sync_body':
        'Everything you do is saved on this phone first. When there is internet, it is shared with your family.',
    'sync_pending': 'Waiting to be shared: {count}',
    'sync_attention': 'Could not be shared: {count}',
    'sync_last': 'Last shared: {time}',
    'sync_never': 'Not shared yet',
    'sync_now': 'Sync now',
    'sync_running': 'Sharing…',
    'sync_ok': 'Everything is up to date.',
    'sync_repair':
        'This phone needs a new pairing code from your caregiver to share progress. Activities still work.',
    // Privacy
    'privacy_title': 'Privacy',
    'privacy_on_phone_title': 'Kept on this phone',
    'privacy_on_phone_body':
        'Your activities, approved memories and photos, and daily routines.',
    'privacy_shared_title': 'Shared with your family',
    'privacy_shared_body':
        'Activity progress is shared with your caregivers. A clinician sees it only if your family allows it.',
    'privacy_not_saved_title': 'Never saved',
    'privacy_not_saved_body':
        'The words you type to the helper are not saved anywhere.',
    'privacy_consent_title': 'Your choices',
    'privacy_consent_unknown':
        'Not known yet. Connect to the internet and tap Check again.',
    'privacy_consent_granted': 'Allowed',
    'privacy_consent_withdrawn': 'Not allowed',
    'privacy_consent_none': 'Not recorded',
    'privacy_consent_change':
        'To change these choices, please ask your caregiver.',
    'privacy_consent_checked': 'Checked: {time}',
    'privacy_refresh': 'Check again',
    'privacy_refresh_failed':
        'Could not check right now. Showing the last known choices.',
    'privacy_remove': 'Remove this person from this phone',
    'privacy_remove_title': 'Remove {name} from this phone?',
    'privacy_remove_body':
        "This deletes their activities, memories and photos from this phone only. Nothing is deleted from the family's SNEHA account.",
    'privacy_remove_unsynced':
        '{count} activities have not been shared yet and will be lost.',
    'privacy_remove_confirm': 'Yes, remove',
    'consent_data_processing': 'Saving activities and memories',
    'consent_clinician_sharing': 'Sharing with a clinician',
    'consent_cloud_ai': 'Online AI helper',
    'consent_voice_processing': 'Voice features',
    // Suggestions (on-device engagement rules; never a test)
    'suggest_title': 'Suggested for you',
    'suggest_device': 'Chosen on this phone',
    'suggest_server': 'Chosen for you',
    'suggest_start': 'Start',
    'suggest_break_title': 'Time for a rest',
    'suggest_break_body':
        'You said you are tired. Rest for about {minutes} minutes, or try something easy.',
    'suggest_easy': 'Try something easy',
    'suggest_none': 'Nothing to suggest yet. You can choose an activity.',
    'suggest_loading': 'Finding something for you…',
    'suggest_why_interest': 'Matches things you enjoy.',
    'suggest_why_talk': 'Matches what we talked about.',
    'suggest_why_enjoyed': 'You enjoyed this before.',
    'suggest_why_easy': 'An easy one, so you can take it gently.',
    'suggest_why_hints': 'Help will come a little sooner this time.',
    'suggest_why_gentler': 'Something gentler for today.',
    'suggest_why_read_aloud': 'Each question will be read aloud for you.',
    'suggest_why_new': 'A good one to start with.',
    'suggest_why_change': 'Something different for a change.',
    'suggest_why_memories': 'Uses your family photos.',
    'suggest_why_routine': 'Uses your own daily routine.',
    'suggest_why_familiar': 'One you know well.',
    'suggest_why_default': 'A good one to try.',
    // Tiredness and feedback
    'runner_tired': "I'm tired",
    // Memory-based activities (activities/memory_content.dart). Every sentence
    // is filled only with what the family entered and approved.
    'hint_relationship': '{name} is your {relationship}.',
    'game_sort_memory_q': 'What does this photo show?',
    'memory_kind_person': 'A person',
    'memory_kind_place': 'A place',
    'memory_kind_event': 'A special day',
    'memory_kind_object': 'A thing',
    'story_q_person_rel':
        'This is {name}, your {relationship}. What do you remember about them?',
    'story_q_person': 'This is {name}. What do you remember about them?',
    'story_q_place': 'This is {title}. What do you remember about this place?',
    'story_q_event': 'This is {title}. What do you remember about that day?',
    'story_q_object': 'This is {title}. Where did it come from?',
    'story_fact_person_in': '{name} was there too.',
    'story_fact_located_at': 'This was at {place}.',
    // In-activity comfort (adaptation/session_policy.dart)
    'runner_auto_hint': 'Here is a little help.',
    'runner_shortened': "Let's finish soon. Just a little more.",
    'runner_break_title': 'Shall we rest?',
    'runner_break_body': 'That was a tricky one. A short rest can help.',
    'runner_break_rest': 'Rest now',
    'runner_break_continue': 'Keep going',
    // Caregiver controls (on the patient's phone)
    'caregiver_button': 'Caregiver',
    'home_caregiver': 'For caregivers',
    'caregiver_title': 'For caregivers',
    'caregiver_intro':
        'Things a family member or helper can do for {name}. Everything here works without the internet.',
    'caregiver_report_tiredness': 'Report tiredness',
    'caregiver_section_today': 'Today',
    'caregiver_section_phone': 'This phone and privacy',
    'caregiver_sheet_title': 'How does {name} seem?',
    'caregiver_sheet_body':
        'Your answer changes this activity now and the next suggestions.',
    'caregiver_mild': 'A little tired: make it easier',
    'caregiver_severe': 'Very tired: stop now',
    'caregiver_cancel': 'Cancel',
    'caregiver_reported_mild':
        'Thank you. Activities will be easier for a while.',
    'caregiver_reported_severe':
        'Thank you. The next suggestion will be a rest.',
    'result_tired_title': "Let's take a rest",
    'result_tired_body': 'Thank you for telling us. Resting is a good idea.',
    'result_rest': 'Rest now',
    'result_easy': 'Try something easy',
    'result_enjoy_question': 'Did you enjoy this?',
    'result_enjoy_yes': 'Enjoyed it',
    'result_enjoy_ok': 'It was OK',
    'result_enjoy_no': 'Not really',
    'result_enjoy_skip': 'Skip this question',
    'result_enjoy_thanks': 'Thank you for telling us.',
    // Local progress (descriptive only)
    'home_progress': 'What I have done',
    'progress_title': 'What I have done',
    'progress_note':
        'This shows what you have played on this phone. It is not a test.',
    'progress_empty': 'Nothing played yet. Your activities will appear here.',
    'progress_level': 'Level {level} of {max}',
    'progress_played': 'Played {count} times',
    'progress_played_one': 'Played {count} time',
    'progress_last': 'Last played: {date}',
    'progress_enjoyed': 'Enjoyed: {count}',
    // Sync problems (local copies are always kept)
    'sync_attention_title': 'Could not be shared',
    'sync_attention_conflict':
        'The server already has a different copy. Your copy is kept on this phone.',
    'sync_attention_rejected':
        'The server could not accept this yet. Your copy is kept on this phone.',
    'sync_attention_failed':
        'We tried several times without success. Your copy is kept on this phone.',
    'sync_retry': 'Try again',
    'sync_waiting': 'Waiting to try again later: {count}',
    'sync_entity_activity_result': 'An activity',
    'sync_entity_activity_session': 'An activity session',
    'sync_entity_conversation': 'A chat summary',
    'sync_entity_personalization_state': 'Activity levels',
    'sync_entity_other': 'An item',
    // Speech
    'speech_read_aloud': 'Read aloud',
    'speech_input_unavailable':
        'Talking by voice is not available yet. Please type or tap a reply.',
    'speech_lang_unsupported': 'This phone has no voice for your language.',
    'speech_mic_start': 'Speak',
    'speech_mic_stop': 'Stop and use my words',
    'speech_listening':
        'Listening… Tap the microphone again when you have finished.',
    'speech_transcribing': 'Writing down your words…',
    'speech_check_text': 'Please check the words, then tap Send.',
    'speech_no_consent':
        'Talking by voice needs permission from your family first. Please type or tap a reply.',
    'speech_lang_no_asr':
        'Talking by voice is not available for your language yet. Please type or tap a reply.',
    'speech_server_missing':
        'Talking by voice is not ready yet. Please type or tap a reply.',
    'speech_offline':
        'Talking by voice needs an internet connection. Please type or tap a reply.',
    'speech_no_mic_permission':
        'SNEHA is not allowed to use the microphone. Please type or tap a reply.',
    'speech_bad_audio':
        'Sorry, that recording could not be used. Please try again or type.',
    'speech_nothing_heard': 'No words were heard. Please try again or type.',
    'speech_failed':
        'Talking by voice did not work this time. Please type or tap a reply.',
    'speech_engine_unavailable': 'This phone cannot read aloud.',
    'speech_off': 'Read aloud is turned off in Settings.',
    'speech_not_played': 'Could not read aloud. The words are on the screen.',
    'settings_read_aloud': 'Read aloud',
    'settings_read_aloud_body': 'Read instructions and questions aloud.',
  };

  // DRAFT translations — machine-assisted, NOT yet reviewed by native
  // speakers. Review before release; keep keys in sync with `english`.
  static const _hindi = <String, String>{
    'welcome_title': 'नमस्ते',
    'welcome_start': 'शुरू करें',
    'common_continue': 'आगे बढ़ें',
    'common_back': 'वापस',
    'home_greeting': 'नमस्ते, {name}',
    'home_play': 'कोई खेल खेलें',
    'home_memories': 'यादें देखें',
    'home_talk': 'सहायक से बात करें',
    'home_settings': 'सेटिंग्स',
    'conn_online': 'जुड़ा हुआ है',
    'conn_offline': 'इस फ़ोन पर चल रहा है',
    'runner_pause': 'रुकें',
    'runner_resume': 'जारी रखें',
    'runner_hint': 'संकेत',
    'runner_skip': 'छोड़ें',
    'runner_stop': 'बंद करें',
    'result_title_done': 'बहुत बढ़िया!',
    'result_title_stopped': 'खेलने के लिए धन्यवाद',
    'result_home': 'होम पर जाएँ',
    'language_title': 'अपनी भाषा चुनें',
    'settings_title': 'सेटिंग्स',
    'settings_text_size': 'अक्षरों का आकार',
    'activities_title': 'कोई गतिविधि चुनें',
    'profiles_title': 'SNEHA कौन इस्तेमाल कर रहा है?',
    'talk_reply_stop':
        'ठीक है, अब हम रुक सकते हैं। मेरे साथ समय बिताने के लिए धन्यवाद।',
    'talk_reply_tired': 'चलिए थोड़ा आराम करते हैं।',
    'talk_reply_scared':
        'मुझे दुख है कि आप ऐसा महसूस कर रहे हैं। कृपया अभी परिवार के किसी सदस्य को फ़ोन करें। आपातकाल में 112 पर कॉल करें।',
  };

  // DRAFT — needs native-speaker review.
  static const _assamese = <String, String>{
    'welcome_title': 'নমস্কাৰ',
    'welcome_start': 'আৰম্ভ কৰক',
    'common_continue': 'আগবাঢ়ক',
    'common_back': 'উভতি যাওক',
    'home_greeting': 'নমস্কাৰ, {name}',
    'home_play': 'এটা খেল খেলক',
    'home_memories': 'স্মৃতিবোৰ চাওক',
    'home_talk': 'সহায়কৰ সৈতে কথা পাতক',
    'home_settings': 'ছেটিংছ',
    'conn_online': 'সংযোগ হৈ আছে',
    'conn_offline': 'এই ফোনতে চলি আছে',
    'runner_pause': 'ৰখক',
    'runner_resume': 'অব্যাহত ৰাখক',
    'runner_hint': 'ইংগিত',
    'runner_skip': 'এৰি দিয়ক',
    'runner_stop': 'বন্ধ কৰক',
    'result_title_done': 'বৰ ভাল!',
    'result_title_stopped': 'খেলাৰ বাবে ধন্যবাদ',
    'result_home': 'মূল পৃষ্ঠালৈ যাওক',
    'language_title': 'আপোনাৰ ভাষা বাছক',
    'settings_title': 'ছেটিংছ',
    'settings_text_size': 'আখৰৰ আকাৰ',
    'activities_title': 'এটা কাৰ্যকলাপ বাছক',
    'profiles_title': 'SNEHA কোনে ব্যৱহাৰ কৰিছে?',
    'talk_reply_stop': 'ঠিক আছে, এতিয়া আমি ৰখিব পাৰো।',
    'talk_reply_tired': 'অলপ জিৰণি লওঁ আহক।',
    'talk_reply_scared':
        'আপুনি এনে অনুভৱ কৰিছে বুলি মই দুখিত। অনুগ্ৰহ কৰি এতিয়াই পৰিয়ালৰ কাৰোবাক ফোন কৰক। জৰুৰীকালীন অৱস্থাত 112 ত ফোন কৰক।',
  };

  // DRAFT — needs native-speaker review.
  static const _bengali = <String, String>{
    'welcome_title': 'নমস্কার',
    'welcome_start': 'শুরু করুন',
    'common_continue': 'এগিয়ে যান',
    'common_back': 'ফিরে যান',
    'home_greeting': 'নমস্কার, {name}',
    'home_play': 'একটি খেলা খেলুন',
    'home_memories': 'স্মৃতিগুলো দেখুন',
    'home_talk': 'সহায়কের সঙ্গে কথা বলুন',
    'home_settings': 'সেটিংস',
    'conn_online': 'সংযুক্ত',
    'conn_offline': 'এই ফোনেই চলছে',
    'runner_pause': 'থামুন',
    'runner_resume': 'চালিয়ে যান',
    'runner_hint': 'ইঙ্গিত',
    'runner_skip': 'বাদ দিন',
    'runner_stop': 'বন্ধ করুন',
    'result_title_done': 'খুব ভালো!',
    'result_title_stopped': 'খেলার জন্য ধন্যবাদ',
    'result_home': 'হোমে যান',
    'language_title': 'আপনার ভাষা বেছে নিন',
    'settings_title': 'সেটিংস',
    'settings_text_size': 'লেখার আকার',
    'activities_title': 'একটি কার্যকলাপ বেছে নিন',
    'profiles_title': 'SNEHA কে ব্যবহার করছেন?',
    'talk_reply_stop': 'ঠিক আছে, এখন আমরা থামতে পারি।',
    'talk_reply_tired': 'চলুন একটু বিশ্রাম নিই।',
    'talk_reply_scared':
        'আপনার এমন লাগছে শুনে আমি দুঃখিত। দয়া করে এখনই পরিবারের কাউকে ফোন করুন। জরুরি অবস্থায় 112-এ ফোন করুন।',
  };

  static const _tables = <String, Map<String, String>>{
    'hi': _hindi,
    'as': _assamese,
    'bn': _bengali,
  };

  /// Exposed for tests: every draft key must exist in English.
  static Map<String, Map<String, String>> get draftTables => _tables;
}
