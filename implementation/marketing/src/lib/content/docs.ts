/**
 * Documentation articles, at `/docs/<category>/<slug>`.
 *
 * See `types.ts` for the honesty rules. These are how-tos derived from what the operator
 * console and the desktop crates actually do; a workflow that could not be verified in the
 * code is not written. Where the console shows a control that is disabled or "not available
 * in this build yet", the article says so rather than describing it as a feature.
 */
import {
  articlePath,
  articlesIn,
  articleNeighbours,
  findArticle,
  findCategory,
  relatedIn,
  type KnowledgeCollection,
} from './knowledge.ts'
import type { KnowledgeArticle, KnowledgeCategory } from './types.ts'


export const docsCategories: readonly KnowledgeCategory[] = [
  { id: 'getting-started', title: 'Getting Started', icon: '🚀', desc: 'How live control works, and how SelahCue saves your work' },
  { id: 'display-outputs', title: 'Display & Outputs', icon: '🖥️', desc: 'Assigning screens, the stage display and NDI' },
  { id: 'scripture-bibles', title: 'Scripture & Bibles', icon: '📖', desc: 'Finding verses and the translations included' },
  { id: 'timers-plans', title: 'Timers & Service Plans', icon: '⏱️', desc: 'Building a run sheet and running the service countdown' },
  { id: 'mobile-control', title: 'Mobile Control', icon: '📱', desc: 'Pairing a phone on your local network and what it can do' },
  { id: 'troubleshooting', title: 'Troubleshooting', icon: '🔧', desc: 'What the on-screen status messages mean' },
]

export const docsArticles: readonly KnowledgeArticle[] = [
  // ------------------------------------------------------------------ getting started
  {
    category: 'getting-started',
    slug: 'preview-live-and-go-live',
    startHere: true,
    title: 'Preview, Live and Go Live',
    summary:
      'SelahCue separates what you are preparing from what the audience sees. Learn the one rule behind it and the keys that drive it.',
    body: [
      {
        type: 'p',
        text: 'The Live Console has two panels side by side: **Preview · Staged** and **Live · On air**. Everything you prepare goes to Preview first. Only **Go Live** puts it on the audience screen. Staging never changes what the audience sees.',
      },
      { type: 'h2', text: 'Stage something' },
      {
        type: 'p',
        text: 'Staging means getting something ready without showing it yet. You stage by clicking a plan row, clicking a slide, or moving to the next or previous plan item. In the Scriptures tab, the up and down arrow keys stage each verse as you move.',
      },
      { type: 'h2', text: 'Go live' },
      {
        type: 'p',
        text: 'Press [[Enter]] or click **GO LIVE** to send the staged item to the audience screen. If nothing is staged, nothing happens. Going live also releases a blackout.',
      },
      {
        type: 'callout',
        variant: 'tip',
        title: 'Stage and go live in one move',
        text: 'Double-click a verse in the Scriptures tab to stage it and send it live in one gesture. Double-click a slide card to put that slide live.',
      },
      { type: 'h2', text: 'Blackout and clear' },
      {
        type: 'ul',
        items: [
          '**Blackout** ([[B]] on the Live Console, [[Ctrl]]+[[Shift]]+[[B]] anywhere, or the **Blackout** button) makes the audience screens go black. The content is kept, so toggling it again, or pressing **Restore output**, brings it straight back.',
          '**Clear Output** (press [[Esc]] twice within a second on the Live Console, press [[Ctrl]]+[[Shift]]+[[.]] anywhere, or click the button) empties the live output. It leaves Preview alone and also releases a blackout.',
        ],
      },
      { type: 'h2', text: 'Keys for live control' },
      {
        type: 'ul',
        items: [
          '[[Space]] or [[→]]: next item. This stages it; it does not go live.',
          '[[←]]: previous item (also staged only).',
          '[[Enter]]: go live.',
          '[[B]]: toggle blackout.',
          '[[Esc]] [[Esc]]: clear the live output. [[Backspace]] does the same today.',
        ],
      },
      { type: 'h3', text: 'Emergency controls work everywhere' },
      {
        type: 'ul',
        items: [
          '[[Ctrl]]+[[Shift]]+[[B]] ([[⌘]]+[[Shift]]+[[B]] on a Mac): toggle blackout.',
          '[[Ctrl]]+[[Shift]]+[[.]] ([[⌘]]+[[Shift]]+[[.]] on a Mac): clear the live output.',
          'The **Blackout** and **Clear Output** buttons along the bottom of the window.',
        ],
      },
      {
        type: 'p',
        text: 'The two chords work from every screen, even while you are typing in a field, and the buttons are on every screen. A blackout or a clear is never more than one action away.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'When the single keys work',
        text: 'The single keys above (Space, the arrows, Enter, B, Esc Esc and Backspace) act on the Live Console only, so moving around Settings or Screens & Outputs cannot advance the show by accident. They are ignored while you are typing in a field, and a button that has keyboard focus keeps Enter and Space for itself. Remapping keys is not available yet.',
      },
    ],
  },
  {
    category: 'getting-started',
    slug: 'offline-and-autosave',
    title: 'Working offline and how autosave works',
    summary:
      'What runs with no network, how often SelahCue saves, what happens after a crash, and the status notices you may see when you relaunch.',
    body: [
      { type: 'h2', text: 'What works with no network' },
      {
        type: 'ul',
        items: [
          'Service plans, Preview and Live, blackout and clear, timers and your output windows.',
          'Scripture: KJV, WEB, ASV, WEBBE and Darby are built into the app, so lookup and search work offline.',
          'On-device speech-to-text, after its model has been downloaded once.',
        ],
      },
      {
        type: 'p',
        text: 'The speech model is downloaded the first time you press **Start listening**, and that needs an internet connection once. After the download finishes, transcription works fully offline.',
      },
      { type: 'h2', text: 'How autosave works' },
      {
        type: 'p',
        text: 'Autosave is always on. SelahCue saves when something changes, at most once a second, and re-saves a running countdown every five seconds. The Storage settings state that at most five seconds of work is lost on a forced shutdown. It also keeps the last three restore points, captured at most once a minute.',
      },
      { type: 'h2', text: 'After a crash or restart' },
      {
        type: 'p',
        text: 'When you relaunch, SelahCue restores your session without asking: the plan, what was live and staged, whether the output was blacked out, and a running countdown. You will see a dismissible notice:',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Session restored',
        text: 'Your plan, themes, slides and edits were restored from the last autosave.',
      },
      {
        type: 'p',
        text: 'If SelahCue is launched three times within 60 seconds without staying up (a run counts as stable after 10 seconds or a clean exit), it starts clean instead and leaves your previous session untouched. The notice reads **Started clean after repeated restarts**, and it tells you to relaunch once the run is stable to resume.',
      },
      { type: 'h2', text: 'Where your data is kept' },
      {
        type: 'ul',
        items: [
          '**macOS:** `~/Library/Application Support/SelahCue`',
          '**Windows:** `%APPDATA%\\SelahCue`',
          '**Linux:** `$XDG_DATA_HOME/selahcue`, or `~/.local/share/selahcue`',
        ],
      },
      {
        type: 'p',
        text: 'That folder holds the main database, `selahcue.db3`. The deck library and Providers & Privacy settings live in a second store in the operator’s own application-data folder, so there is not a single data folder yet.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'Not available yet',
        text: '**Back up now**, **Run check** and **Restore** appear in Settings under Storage but are disabled in this build. SelahCue does not write log files, and **Export diagnostics** is disabled too. There is no manual resume-or-start-clean choice after a crash; the behaviour above is automatic.',
      },
    ],
  },

  // -------------------------------------------------------------- display & outputs
  {
    category: 'display-outputs',
    slug: 'assign-displays-to-outputs',
    title: 'Assign displays to outputs',
    summary:
      'Choose which monitor shows the audience screen and which shows the stage display, and what each kind of output is for.',
    body: [
      { type: 'h2', text: 'The outputs' },
      {
        type: 'ul',
        items: [
          '**Audience — Main**: what the congregation sees. It gets its own window.',
          '**Stage Display**: the screen for the people on the platform. It also gets its own window.',
          '**Lower Third** and **Livestream Program**: virtual feeds with no window. Their delivery is NDI (see [Send an output over NDI](/docs/display-outputs/ndi-output)).',
        ],
      },
      { type: 'h2', text: 'Assign a monitor' },
      {
        type: 'ol',
        items: [
          'Open **Screens & Outputs** from the left navigation.',
          'Click the output’s card, or its **Configure** button.',
          'In the inspector on the right, find the **Display** section and open the **Monitor** dropdown.',
          'Choose the monitor. An output with a monitor assigned fills that monitor as a borderless full-screen window. An output with none is an ordinary window you can move.',
        ],
      },
      {
        type: 'p',
        text: 'The Monitor dropdown only appears for Audience — Main and Stage Display, and only when the system reported displays. Otherwise the row reads **No displays found** or **No physical output**.',
      },
      { type: 'h2', text: 'Turn an output on or off' },
      {
        type: 'p',
        text: 'Each card has an on/off toggle that opens or closes that output’s window. Closing a window with its own close button does the same.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'Closing the last window quits SelahCue',
        text: 'The output windows belong to the application. When you close the last one, SelahCue quits. Turn an output off from its card if you only mean to hide it.',
      },
      { type: 'h2', text: 'Work out which screen is which' },
      {
        type: 'p',
        text: 'Click **Identify** (on the Screens & Outputs page, or under Settings, Outputs & Displays). It marks each open output window for about five seconds: one vertical bar on the main output and two on the stage display.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Not available yet',
        text: 'Several controls are shown but disabled in this build, including test patterns, output health, per-output configuration and venue profiles. Phones cannot assign displays; only the desktop operator can. This article covers what works today.',
      },
    ],
  },
  {
    category: 'display-outputs',
    slug: 'stage-display',
    title: 'Set up the stage display',
    summary:
      'Send the stage screen to its own monitor, pick a layout, and send short messages to the people on the platform.',
    body: [
      {
        type: 'p',
        text: 'The stage display (also called the confidence display) is for the people leading from the platform. It shows what is live now, what is next, the time and the service countdown. The audience never sees any of it.',
      },
      { type: 'h2', text: '1. Give it a monitor' },
      {
        type: 'p',
        text: 'Assign a display to the **Stage Display** output as described in [Assign displays to outputs](/docs/display-outputs/assign-displays-to-outputs).',
      },
      { type: 'h2', text: '2. Choose a layout' },
      {
        type: 'p',
        text: 'In the Live Console, open the **Service Timer** tab in the right-hand panel and select its **Stage** sub-tab. Under **Stage theme**, choose one of three layouts:',
      },
      {
        type: 'ul',
        items: [
          '**Worship**: the current line, a **NEXT** line, and a service-timer band.',
          '**Scripture**: the verse, the next line and a **time left** panel with an on-time, hurry or time-up status.',
          '**Timer-only**: a large countdown with the date, and an **over by** count after time runs out.',
        ],
      },
      {
        type: 'p',
        text: 'Settings, under Appearance, has a **Default stage theme** with the same three choices.',
      },
      { type: 'h2', text: '3. Send a message to the stage' },
      {
        type: 'p',
        text: 'Under **Stage message**, tap a preset (**Wrap up, 2 min left**, **Slow down**, **Wrap up now** or **Great job**) or type your own, up to 120 characters. Press **Send to stage**. The message appears over the stage display as **Message from production**. Press **Clear** to remove it.',
      },
      { type: 'h2', text: 'What the stage display shows' },
      {
        type: 'ul',
        items: [
          'The live line and the next line.',
          'The date and time of day.',
          'The service countdown and its **TIME UP** state. See [Run the service timer](/docs/timers-plans/service-timer).',
          'Messages from production.',
        ],
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Limits in this build',
        text: 'Stage text size and the choice of which items appear on the stage display are fixed; those controls are shown disabled. The stage output has no NDI option.',
      },
    ],
  },
  {
    category: 'display-outputs',
    slug: 'ndi-output',
    title: 'Send an output over NDI',
    summary:
      'Publish the audience, lower-third or stream output as an NDI source on your local network, and know the limits before you plan around it.',
    body: [
      {
        type: 'callout',
        variant: 'warning',
        title: 'Check your build first',
        text: 'NDI is included in the Windows installer. A build made without it shows these settings but transmits nothing; the inspector then reads **NDI runtime unavailable** and the toggle is disabled.',
      },
      { type: 'h2', text: 'Turn it on' },
      {
        type: 'ol',
        items: [
          'Open **Screens & Outputs** and select **Audience — Main**, **Lower Third** or **Livestream Program**. The stage display has no NDI option.',
          'In the inspector, find **NDI Output**.',
          'Type a **Source name** (up to 64 characters). Two outputs cannot broadcast under the same name.',
          'Turn on **Broadcast as NDI**. The status line reads **Broadcasting NDI** with your source name, and the output’s card shows an **NDI** pill.',
          'Choose a frame rate: 24, 30, 48, 50 or 60.',
        ],
      },
      { type: 'h2', text: 'On the receiving computer' },
      {
        type: 'p',
        text: 'SelahCue’s own interface says the feed can be received by software such as OBS and vMix, or by another SelahCue. Look for the source name you chose in that program’s NDI source list. What the receiving program needs installed is described by its makers.',
      },
      { type: 'h2', text: 'How it behaves' },
      {
        type: 'ul',
        items: [
          'Frames are 1920 by 1080.',
          '**Blackout** also blacks out every NDI feed, so the stream matches the room.',
          'Lower Third and Livestream Program exist only as NDI feeds; they have no window.',
        ],
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Known limits',
        text: 'Every frame is opaque. The Lower Third output is not sent with an alpha channel, so it will not key over other video. There is no macOS or Linux installer yet, so the Windows installer is the only packaged build that includes NDI. We do not publish latency figures for NDI.',
      },
    ],
  },

  // ------------------------------------------------------------ scripture & bibles
  {
    category: 'scripture-bibles',
    slug: 'find-and-stage-a-verse',
    startHere: true,
    title: 'Find and stage a verse',
    summary:
      'Type a reference or keywords, open the chapter, stage a verse or a range, and send it live.',
    body: [
      { type: 'h2', text: 'Open the Scriptures tab' },
      {
        type: 'p',
        text: 'Choose **Scriptures** in the Live Console (or press [[Ctrl]]+[[6]], [[⌘]]+[[6]] on a Mac). Pick a translation from the picker, which lists them by code, then use the search box labelled **Reference or keywords**.',
      },
      { type: 'h2', text: 'Type a reference' },
      {
        type: 'ul',
        items: [
          '`Romans 8:28`, `Rom 8:28-30`, `Psalm 23:1-6`, `1 Cor 13:4`, `Jn 3:16`',
          'Capitals and full stops do not matter: `rom. 8:28` works. So does `First John 1:9`, `I John 1:9` and `Song of Solomon 2:1`.',
          'Spaces can stand in for the colon: `gen 1 1` or `1 cor 13 4`.',
        ],
      },
      {
        type: 'p',
        text: 'A bare book name such as `Romans` does not open anything, and `Jude 9` is read as chapter 9, so write `Jude 1:9`. Ranges must stay inside one chapter.',
      },
      { type: 'h2', text: 'Search by keyword' },
      {
        type: 'p',
        text: 'Type words instead of a reference and SelahCue lists verses that contain every word you typed, in Bible order, up to eight. Words are matched as plain text, so a short word also matches longer words that contain it. There is no ranking and no exact-phrase search.',
      },
      { type: 'h2', text: 'Stage and go live' },
      {
        type: 'ol',
        items: [
          'Press [[Enter]] on a result to open the chapter. A reference to a whole chapter, such as `Ps 23`, stages verse 1.',
          'Move through the verses with [[↑]] and [[↓]]. Each one is staged to Preview as you go.',
          'Press [[Enter]] to send the staged verse live, or double-click a verse to stage it and go live in one move.',
        ],
      },
      {
        type: 'p',
        text: 'A range such as `Rom 8:28-30` goes onto one slide titled, for example, **Romans 8:28-30 (KJV)**, with verse numbers in front of each verse. If the verse does not exist in that translation, you are told and nothing is staged.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'If a verse is already live',
        text: 'When scripture is already on air, clicking or arrowing to a different verse moves Live to that verse as well. Stage from a chapter you are not live on, or blackout first, if you want to look ahead without the audience following.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Not available yet',
        text: 'Long passages are not split across slides; the whole passage goes on one slide and its text shrinks to fit. Scripture history and favourites are shown disabled in Settings. A search that contains several references separated by a semicolon returns one result per reference, and you open them one at a time.',
      },
    ],
  },
  {
    category: 'scripture-bibles',
    slug: 'included-translations',
    title: 'Included Bible translations',
    summary:
      'The five translations built into SelahCue, which one the console opens on, and what is not available in this build.',
    body: [
      { type: 'h2', text: 'What is included' },
      {
        type: 'ul',
        items: [
          '**KJV**: the King James Version, the translation the console opens on.',
          '**WEB**: the World English Bible.',
          '**ASV**: the American Standard Version.',
          '**WEBBE**: the World English Bible, British Edition.',
          '**DBY**: the Darby translation.',
        ],
      },
      {
        type: 'p',
        text: 'They are part of the application, so they work with no download and no connection. The About page lists them as public domain. The canon is the 66 books of the Protestant Bible; the Apocrypha is not included.',
      },
      { type: 'h2', text: 'Switch translation' },
      {
        type: 'p',
        text: 'Use the translation picker in the Scriptures tab. It shows the codes above. Settings has a **Scripture & Translations** page that lists what is installed, but its **Default translation** control does not change the translation the console opens on yet; the console always opens on KJV.',
      },
      { type: 'h2', text: 'What you may see but cannot use' },
      {
        type: 'ul',
        items: [
          'Settings and About may list **Young’s Literal Translation (YLT)**. It is not installed and cannot be downloaded in this build.',
          'Licensed translations such as NIV, ESV and NLT are not available. The Settings page says importing a licensed module or connecting a licensed service is **Not available in this build yet**.',
        ],
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'Adding text yourself',
        text: 'SelahCue does not supply a licence for any translation. If you put text from a translation that is not public domain on a slide yourself, make sure you have permission to use it.',
      },
    ],
  },

  // --------------------------------------------------------------- timers & plans
  {
    category: 'timers-plans',
    slug: 'build-a-service-plan',
    title: 'Build a service plan',
    summary:
      'Create the run sheet for the service: start from a template or paste a list, add and order items, and link scripture and presentations.',
    body: [
      { type: 'h2', text: 'Open the plan' },
      {
        type: 'p',
        text: 'Choose **Service Plan** in the navigation. It has three columns: **Add item**, the **Run sheet**, and a panel that shows either the plan summary or the selected item.',
      },
      { type: 'h2', text: 'Start a plan' },
      {
        type: 'ul',
        items: [
          '**Create a service…** starts an empty plan.',
          '**Start from a template…** offers two templates: Sunday Morning and Midweek Gathering.',
          '**Import a run sheet…** takes pasted text, one item per line, each starting with its type. For example: `Announcement: Welcome`, `Song: Great Are You Lord`, `Scripture: Romans 8:28`, `Section: Sermon`.',
        ],
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'One plan at a time',
        text: 'Creating, starting from a template and importing all replace the plan that is open. This build keeps one plan at a time.',
      },
      { type: 'h2', text: 'Add and arrange items' },
      {
        type: 'ol',
        items: [
          'Press an add button: **Song**, **Scripture**, **Presentation**, **Media**, **Announcement**, **Timer** or **Section**. The item is added at the end and selected.',
          'Rename it in the **Title** field and press [[Enter]].',
          'Reorder by dragging the ⠿ handle, with the ↑ and ↓ buttons on a row, or with [[Alt]]+[[↑]] and [[Alt]]+[[↓]] on a focused row.',
          'Remove an item with **Remove item**, which asks you to confirm.',
        ],
      },
      { type: 'h2', text: 'Link content' },
      {
        type: 'p',
        text: 'Scripture and Presentation items can be linked: use **Link a scripture…** or **Link a presentation…**, then **Change…** or **Unlink** later. The linked content is what goes to Preview when you stage that item.',
      },
      { type: 'h2', text: 'Plan actions' },
      {
        type: 'ul',
        items: [
          '**Duplicate this service** copies the whole open plan (not one item).',
          '**Publish to team** hands the plan to the Live Console on this computer. It does not send it to anyone else.',
          '**Open in Live** switches to the Live Console.',
        ],
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Limits and what is not here yet',
        text: 'A plan holds up to 500 items, and a title can be 120 characters. Song lyrics cannot be typed in yet, so a song item shows only its title. Item owner and duration are read-only. A **Timer** item is a label: it does not start a timer (see [Run the service timer](/docs/timers-plans/service-timer)). Section items are labels too, and Next and Previous do not skip them. There is no Save as template.',
      },
    ],
  },
  {
    category: 'timers-plans',
    slug: 'service-timer',
    title: 'Run the service timer',
    summary:
      'Start a countdown, adjust it as the service moves, and see where it appears. There is one timer, and the audience never sees it.',
    body: [
      { type: 'h2', text: 'Start a countdown' },
      {
        type: 'p',
        text: 'In the Live Console, open the **Service Timer** tab in the right-hand panel and select **Timer**.',
      },
      {
        type: 'ul',
        items: [
          'Under **Set a custom time**, fill in hours, minutes and seconds (up to 23:59:59) and press **Start**.',
          'Or press one of the presets, **5:00** or **10:00**.',
        ],
      },
      { type: 'h2', text: 'Control it' },
      {
        type: 'ul',
        items: [
          '**− 1:00** and **+ 1:00** change the target by a minute.',
          '**Pause** and **Resume** stop and restart the countdown.',
          '**Reset** restarts the countdown from its full length, and it runs straight away.',
          '**Stop** removes the timer.',
        ],
      },
      {
        type: 'p',
        text: 'Pause, Reset and the minute buttons stay disabled until a timer exists. Starting a new timer replaces the one that is running.',
      },
      { type: 'h2', text: 'TIME UP' },
      {
        type: 'p',
        text: 'The console shows a status of **Running**, **Paused** or **Time up**, and the readout turns amber at 30 seconds or less. At zero the timer does not stop: it keeps running, and the stage display shows how far over you are (for example, over by 1:12). Taking time off below what has already elapsed puts the timer in TIME UP, and adding time clears it.',
      },
      { type: 'h2', text: 'Where it appears' },
      {
        type: 'ul',
        items: [
          'On the **stage display**, in each of the three layouts.',
          'In the chip at the top of the console, on every screen.',
        ],
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'The audience screen never shows the timer',
        text: 'The timer is for the platform. If you need the congregation to see a countdown, it has to be put on a slide; SelahCue does not send it to the audience output.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Not available yet',
        text: 'Only a single countdown exists: there is no count-up or elapsed timer, no second timer, no sound, and the amber warning point is fixed at 30 seconds. The command palette’s **Start service timer** always starts five minutes. If SelahCue restarts, a running countdown comes back as of the last save, which can be up to five seconds old.',
      },
    ],
  },

  // ------------------------------------------------------------------ mobile control
  {
    category: 'mobile-control',
    slug: 'pair-a-phone',
    title: 'Pair a phone',
    summary:
      'Connect a phone or tablet to SelahCue over your local network: scan the code, approve the device, and choose its role.',
    body: [
      {
        type: 'callout',
        variant: 'info',
        title: 'Before you start',
        text: 'The controller app is not in the app stores yet; it is built from the project today. The phone must be on the same Wi-Fi network as the desktop, and no internet connection is needed.',
      },
      { type: 'h2', text: 'On the desktop' },
      {
        type: 'ol',
        items: [
          'Open **Settings**, choose **Network & Mobile**, and press **Manage devices**. (The shortcut is [[Ctrl]]+[[Shift]]+[[R]], or [[⌘]]+[[Shift]]+[[R]] on a Mac.)',
          'The Remote Control page has a **Pair a device** panel with a QR code, the host fingerprint, and a **Single-use** countdown showing when the code expires.',
        ],
      },
      { type: 'h2', text: 'On the phone' },
      {
        type: 'ol',
        items: [
          'Open the controller app. On **Connect to a host**, choose **Scan the pairing QR** and scan the code on the desktop.',
          'You can change the name the desktop will show for this device.',
          'The phone then shows **Waiting for the host to allow this device**.',
        ],
      },
      {
        type: 'p',
        text: 'The app also lists hosts it discovers on the network. If your network blocks that discovery, scanning the QR code is the way in.',
      },
      { type: 'h2', text: 'Approve it' },
      {
        type: 'p',
        text: 'Back on the desktop, a **Pending** request appears. Choose the device’s **Role** (it starts as Producer) and press **Approve**, or **Deny** if you do not recognise the device. The request expires after about two minutes.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'A code works once, for two minutes',
        text: 'The code is used up the moment a phone connects, even if you then deny it or the request times out. The code is not renewed on its own. Press **New code** for each phone.',
      },
      { type: 'h2', text: 'Manage paired devices' },
      {
        type: 'p',
        text: 'The **Paired devices** table lists each device with its role, when it was last seen, and a status: Online (heard from in the last 30 seconds), Idle (under five minutes) or Offline. You can change a device’s role from its dropdown, and **Revoke** removes it. Revoke asks for a second press to confirm.',
      },
      {
        type: 'p',
        text: 'See [What each phone role can do](/docs/mobile-control/phone-roles). If the phone does not connect, read [My phone will not pair](/support/mobile-control/phone-wont-pair).',
      },
    ],
  },
  {
    category: 'mobile-control',
    slug: 'phone-roles',
    title: 'What each phone role can do',
    summary:
      'Producer, Assistant and Viewer: what a paired phone is allowed to do, what it can never do, and how the phone app behaves.',
    body: [
      { type: 'h2', text: 'Roles' },
      {
        type: 'ul',
        items: [
          '**Producer**: go live, step next and previous, clear, blackout, run the timer, search and stage scripture, approve or dismiss detected verses, and watch the live state and transcript.',
          '**Assistant**: step next and previous, stage items and scripture, and approve detected verses, but only to Preview. It cannot go live, clear, blackout or run the timer.',
          '**Viewer**: watch the live state and transcript only.',
        ],
      },
      {
        type: 'p',
        text: 'The full Operator role belongs to the desktop. You cannot give it to a phone. No phone can edit the plan, send stage messages, change themes or outputs, or manage devices.',
      },
      { type: 'h2', text: 'On the phone' },
      {
        type: 'ul',
        items: [
          'Four tabs: **Live**, **Plan**, **Scripture** and **Timer**. A Viewer has no Scripture tab or emergency strip.',
          '**Blackout** and **Clear all** need a second tap within three seconds, shown as **Confirm blackout** and **Confirm clear**. Un-blackout is a single tap.',
          'Next and Previous stage to Preview, and **Go live** commits. On the Plan tab a tap stages an item and a double-tap goes live (Producers only).',
          'The Preview and Live cards show text titles, not pictures of the slides. The transcript is read-only and shows the last six lines.',
        ],
      },
      { type: 'h2', text: 'If the phone loses the connection' },
      {
        type: 'p',
        text: 'The desktop carries on regardless. The phone shows **Reconnecting to the host… your taps won’t be sent**, keeps its controls disabled, and reads the live state again once it is back. It never queues taps and replays them later.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Changing a role',
        text: 'When you change a phone’s role from the Paired devices table, the desktop applies it to that phone’s next request. The phone’s buttons can lag until it reconnects, so a command may be refused as not allowed in the meantime.',
      },
    ],
  },

  // ------------------------------------------------------------------ troubleshooting
  {
    category: 'troubleshooting',
    slug: 'status-messages',
    title: 'What the on-screen status messages mean',
    summary:
      'A reference for the notices and banners the console shows about saving, displays, the output and NDI, and what to do about each.',
    body: [
      { type: 'h2', text: 'Saving and recovery' },
      {
        type: 'ul',
        items: [
          '**Session restored.** Your plan, themes, slides and edits were restored from the last autosave. Nothing to do; dismiss it with the ✕.',
          '**Started clean after repeated restarts.** SelahCue was launched three times in 60 seconds without staying up, so it started with a clean session. Your previous session is preserved; relaunch once this run is stable to resume it.',
          '**Last autosave failed**, with a reason, and **Your recent work may not be saved.** SelahCue could not write its autosave, and the notice gives the reason. If the cause is low disk space, free some up: SelahCue warns when space is very low and stops writing checkpoints before the disk is full. See [Working offline and how autosave works](/docs/getting-started/offline-and-autosave).',
          '**Couldn’t open the plan…** with **Restore last autosave**. The plan failed to open and a recent autosave is available. Pressing the button asks the host to restore it; the answer is **Restore requested…**, so check that the plan looks right afterwards.',
        ],
      },
      { type: 'h2', text: 'Displays and the live output' },
      {
        type: 'ul',
        items: [
          '**No signal**, **No signal · no monitor attached** and the **Signal lost** banner. The output’s monitor is gone. Other outputs are unaffected. The banner says the output reattaches automatically, with its content, when the display is reconnected. If it does not, reassign the display in Screens & Outputs ([Assign displays to outputs](/docs/display-outputs/assign-displays-to-outputs)).',
          '**Output held: the live output is holding its last good frame.** The renderer hit a fault, and the audience is seeing the last good picture instead of a blank screen. Treat it as a warning and check the output window.',
          '**No displays found** or **No physical output** in an output’s Monitor row: the system reported no displays, or that output kind has no window.',
          '**Output is black: the audience sees nothing.** Blackout is on. Press [[B]] or **Restore output**.',
        ],
      },
      { type: 'h2', text: 'NDI' },
      {
        type: 'ul',
        items: [
          '**NDI runtime unavailable.** This build was made without NDI, so the toggle is disabled. See [Send an output over NDI](/docs/display-outputs/ndi-output).',
          '**Is already broadcasting on another output.** Two outputs cannot share an NDI source name. Rename one.',
        ],
      },
      { type: 'h2', text: 'Service plan' },
      {
        type: 'ul',
        items: [
          '**This build keeps one plan at a time.** Creating, templating or importing replaces the open plan.',
        ],
      },
    ],
  },
]

export const docs: KnowledgeCollection = { root: '/docs', categories: docsCategories, articles: docsArticles }

export const docsPath = (a: KnowledgeArticle): string => articlePath(docs.root, a)
export const findDocsArticle = (category: unknown, slug: unknown) => findArticle(docs, category, slug)
export const findDocsCategory = (id: unknown) => findCategory(docs, id)
export const docsIn = (categoryId: string) => articlesIn(docs, categoryId)
export const docsNeighbours = (a: KnowledgeArticle) => articleNeighbours(docs, a)
export const docsRelated = (a: KnowledgeArticle) => relatedIn(docs, a)
