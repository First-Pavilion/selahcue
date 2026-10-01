/**
 * Support (help centre) articles, at `/support/<category>/<slug>`.
 *
 * See `types.ts` for the honesty rules. Each article answers a question someone is likely
 * to have while running SelahCue, using the exact on-screen wording from the operator
 * console and controller app. Where a cause or fix comes from reading the code rather than
 * running it on hardware, the article is worded as "SelahCue does X" and not as a promise
 * about every network or machine.
 *
 * DELIBERATELY ABSENT: a "Licensing & Billing" category. Billing is not built (the webhook
 * route answers 501), activation is not wired into the desktop app, and there is no
 * deactivate flow, so any article on seats or subscriptions would be describing something
 * that does not exist.
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


export const supportCategories: readonly KnowledgeCategory[] = [
  { id: 'getting-started', title: 'Getting Started', icon: '🚀', desc: 'The audience screen is blank, or something is not appearing' },
  { id: 'display-outputs', title: 'Display & Outputs', icon: '🖥️', desc: 'Screens that are not listed, and NDI that will not switch on' },
  { id: 'scripture-bibles', title: 'Scripture & Bibles', icon: '📖', desc: 'Verses that will not open, and which translations you can use' },
  { id: 'timers-clocks', title: 'Timers & Clocks', icon: '⏱️', desc: 'Where the countdown appears' },
  { id: 'mobile-control', title: 'Mobile Control', icon: '📱', desc: 'Pairing, roles and removing a phone' },
  { id: 'troubleshooting', title: 'Troubleshooting', icon: '🔧', desc: 'Restarts, restored sessions and transcription' },
]

export const supportArticles: readonly KnowledgeArticle[] = [
  // ------------------------------------------------------------------ getting started
  {
    category: 'getting-started',
    slug: 'nothing-on-the-audience-screen',
    startHere: true,
    title: 'Nothing is showing on the audience screen',
    summary: 'Work through the usual reasons the audience screen is blank, starting with the most common.',
    body: [
      { type: 'p', text: 'Check these in order. Each one is something the console tells you about.' },
      {
        type: 'ol',
        items: [
          '**It is staged but not live.** Look at the two panels. If the item is in **Preview · Staged** and **Live · On air** says **Output idle**, press [[Enter]] or click **GO LIVE**. Staging alone never changes the audience screen.',
          '**Blackout is on.** The console says **Output is black: the audience sees nothing. Press B or click to restore.** Press [[B]] or click **Restore output**. Going live also releases a blackout.',
          '**The output was cleared.** **Clear Output** ([[Esc]] twice) empties the live output. Stage the item again and go live.',
          '**The output has no window or no monitor.** Open **Screens & Outputs**, check that the audience output’s toggle is on, and that its **Monitor** is set. See [Assign displays to outputs](/docs/display-outputs/assign-displays-to-outputs).',
          '**The display lost its signal.** A **Signal lost** banner appears and the output’s pill reads **No signal**. Check the cable and the monitor, and see [What the on-screen status messages mean](/docs/troubleshooting/status-messages).',
          '**The keys are not firing.** The live-control keys only work on the Live Console, not on Settings or Screens & Outputs, and not while your cursor is in a text field.',
        ],
      },
      {
        type: 'p',
        text: 'The rule behind most of this is in [Preview, Live and Go Live](/docs/getting-started/preview-live-and-go-live).',
      },
    ],
  },

  // -------------------------------------------------------------- display & outputs
  {
    category: 'display-outputs',
    slug: 'no-display-to-choose',
    title: 'An output has no monitor to choose',
    summary: 'The Monitor dropdown is missing, empty or says no displays found. Here is why, and what to try.',
    body: [
      {
        type: 'ul',
        items: [
          '**It only exists for two outputs.** Only **Audience — Main** and **Stage Display** have a Monitor choice. **Lower Third** and **Livestream Program** are virtual feeds with no window, so their row reads **No physical output**.',
          '**No displays found.** SelahCue builds its list of displays when it starts, so connect and power on your monitors and projectors first. If a display you connected afterwards is missing, restart SelahCue.',
          '**Check the list in Settings.** **Outputs & Displays** lists every display SelahCue knows about and which output it is assigned to.',
        ],
      },
      { type: 'h2', text: 'If two identical projectors swap' },
      {
        type: 'p',
        text: 'SelahCue tells displays apart by their position. If you swap the cables of two identical projectors, open **Screens & Outputs** and assign the displays again.',
      },
      {
        type: 'p',
        text: 'The full steps, including **Identify** to find out which screen is which, are in [Assign displays to outputs](/docs/display-outputs/assign-displays-to-outputs).',
      },
    ],
  },
  {
    category: 'display-outputs',
    slug: 'ndi-toggle-greyed-out',
    title: 'The NDI toggle is greyed out',
    summary: 'Why Broadcast as NDI cannot be switched on, and which builds can broadcast.',
    body: [
      {
        type: 'p',
        text: 'If **Broadcast as NDI** is disabled and the inspector shows **NDI runtime unavailable** with a warning triangle, your build was made without NDI support. The settings are still there, but nothing is transmitted.',
      },
      { type: 'h2', text: 'What to do' },
      {
        type: 'ul',
        items: [
          'Use a build that includes NDI. The Windows installer is built with it and carries the NDI runtime. There is no macOS or Linux installer yet.',
          'Check you selected the right output. NDI is offered for **Audience — Main**, **Lower Third** and **Livestream Program**. The **Stage Display** has no NDI option.',
        ],
      },
      { type: 'h2', text: 'Other things that look like NDI problems' },
      {
        type: 'ul',
        items: [
          'If two outputs use the same **Source name**, the second is refused with a message that it is already broadcasting on another output. Give each a different name.',
          'Settings, under Outputs & Displays, lists **Network outputs** as **Coming soon**. The working control is the **NDI Output** section in the output’s inspector on Screens & Outputs.',
        ],
      },
      {
        type: 'p',
        text: 'The set-up steps are in [Send an output over NDI](/docs/display-outputs/ndi-output).',
      },
    ],
  },

  // ------------------------------------------------------------------ scripture
  {
    category: 'scripture-bibles',
    slug: 'verse-will-not-open',
    title: 'A verse will not open or stage',
    summary: 'The usual reasons a reference does nothing, and how to write it so it works.',
    body: [
      {
        type: 'ul',
        items: [
          '**Only a book name.** `Romans` on its own does not open anything. Add a chapter, such as `Romans 8`, or a verse, `Romans 8:28`.',
          '**A one-chapter book.** `Jude 9` is read as chapter 9. Write `Jude 1:9`.',
          '**A range across chapters.** Ranges must stay inside one chapter: `Rom 8:28-30` works, a range that crosses into the next chapter does not.',
          '**The verse is not in that translation.** SelahCue tells you the verse is not present in the translation you picked, and stages nothing. Try another translation from the picker.',
          '**Several references at once.** `John 3:16; 1 Cor 13:4` gives one result for each reference. Open them one at a time.',
          '**It is a keyword search.** Words that are not a reference are searched as keywords: every word must appear in the verse, and results are listed in Bible order, not ranked.',
        ],
      },
      { type: 'h2', text: 'If the arrow keys move the plan instead' },
      {
        type: 'p',
        text: '[[↑]] and [[↓]] move through verses only once a chapter is open. [[Space]] and [[→]] always step the service plan, not verses. Open the chapter first with [[Enter]] on a search result.',
      },
      {
        type: 'p',
        text: 'More examples are in [Find and stage a verse](/docs/scripture-bibles/find-and-stage-a-verse).',
      },
    ],
  },
  {
    category: 'scripture-bibles',
    slug: 'niv-esv-nlt-not-available',
    title: 'Can I use NIV, ESV or NLT?',
    summary: 'Licensed translations are not available in this build. These are the translations you can use today.',
    body: [
      {
        type: 'p',
        text: 'Not yet. Licensed translations such as NIV, ESV and NLT are not available in this build, and nothing in the app downloads or unlocks them. The Scripture settings say it directly: importing a licensed module or connecting a licensed Bible service is **Not available in this build yet**.',
      },
      { type: 'h2', text: 'What you can use' },
      {
        type: 'p',
        text: 'Five translations are built in and work offline: KJV, WEB, ASV, WEBBE and DBY (Darby). The About page lists them as public domain. See [Included Bible translations](/docs/scripture-bibles/included-translations).',
      },
      { type: 'h2', text: 'Young’s Literal Translation' },
      {
        type: 'p',
        text: 'You may see YLT listed in Settings or About. It is not installed and cannot be downloaded in this build.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'If you add the text yourself',
        text: 'SelahCue does not supply a licence for any translation. If you type text from a translation that is not public domain onto a slide, make sure you have permission to use it.',
      },
    ],
  },

  // ---------------------------------------------------------------------- timers
  {
    category: 'timers-clocks',
    slug: 'timer-not-on-audience-screen',
    title: 'The timer does not show on the audience screen',
    summary: 'That is by design: the countdown is for the stage display. Here is how to see it.',
    body: [
      {
        type: 'p',
        text: 'The service timer appears on the **stage display** and in the chip at the top of the console. The audience screen never shows it. Settings, under Outputs & Displays, shows this as a locked rule for TIME UP: **Locked · stage only**.',
      },
      { type: 'h2', text: 'To see the countdown' },
      {
        type: 'ol',
        items: [
          'Assign a monitor to the **Stage Display** output ([Assign displays to outputs](/docs/display-outputs/assign-displays-to-outputs)).',
          'Start a timer in the **Service Timer** tab ([Run the service timer](/docs/timers-plans/service-timer)).',
          'For a big countdown, choose the **Timer-only** stage theme.',
        ],
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'No stage screen?',
        text: 'The chip at the top of the console always mirrors the readout, so you can follow the countdown there even without a stage display.',
      },
    ],
  },

  // ------------------------------------------------------------------ mobile
  {
    category: 'mobile-control',
    slug: 'phone-wont-pair',
    startHere: true,
    title: 'My phone will not pair',
    summary: 'A checklist for when the controller app cannot connect to the desktop.',
    body: [
      { type: 'p', text: 'Work down this list. Most failures are one of the first four.' },
      {
        type: 'ol',
        items: [
          '**Same network.** The phone must be on the same Wi-Fi as the desktop.',
          '**Keep the Remote Control page open.** The desktop only looks for new pairing requests while that page is open. Find it under Settings, Network & Mobile, **Manage devices**.',
          '**Use a fresh code.** A code lasts two minutes and works once. It is used up the moment a phone connects, even if the request is then denied or times out. Press **New code**; the code is not renewed on its own.',
          '**Approve on the desktop.** The phone shows **Waiting for the host to allow this device**. Choose a role and press **Approve** in the Pending request on the desktop. If nobody does within about two minutes the request expires.',
          '**Scan instead of discover.** If the phone does not list your desktop, your network may be blocking automatic discovery. Scanning the QR code does not rely on it.',
        ],
      },
      { type: 'h2', text: 'What the errors mean' },
      {
        type: 'ul',
        items: [
          '**pairing rejected: forbidden**: the request was denied or timed out. Make a new code and try again.',
          '**pairing rejected: unauthenticated**: the code was wrong, expired or already used.',
          '**That is not a valid SelahCue pairing invite**: what the app scanned or you typed is not a SelahCue invite.',
        ],
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Still failing?',
        text: 'No internet connection is needed, but we have not yet tested pairing on networks that stop devices from talking to each other, which some guest networks do. If everything above checks out, try the desktop and phone on a different network.',
      },
      {
        type: 'p',
        text: 'Full steps: [Pair a phone](/docs/mobile-control/pair-a-phone).',
      },
    ],
  },
  {
    category: 'mobile-control',
    slug: 'phone-cannot-go-live',
    title: 'My phone cannot go live, clear or run the timer',
    summary: 'What a paired phone is allowed to do depends on its role. Here is how to check and change it.',
    body: [
      {
        type: 'p',
        text: 'Only the **Producer** role can go live, clear, blackout and run the timer from a phone. An **Assistant** can step through the plan and stage items, but only to Preview. A **Viewer** can only watch.',
      },
      { type: 'h2', text: 'Change the role' },
      {
        type: 'ol',
        items: [
          'On the desktop, open Settings, Network & Mobile, **Manage devices**.',
          'In the **Paired devices** table, change the device’s role from its dropdown.',
          'If the phone’s buttons have not changed, disconnect and reconnect the app so it picks up the new role.',
        ],
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Why the buttons can look wrong',
        text: 'The desktop applies a role change straight away, but the phone’s buttons update when it reconnects. In between, an Assistant’s Scripture tab can still say double-tap to send live, and the desktop will refuse the go-live as not allowed.',
      },
      {
        type: 'p',
        text: 'No role lets a phone edit the plan, send stage messages or manage devices. See [What each phone role can do](/docs/mobile-control/phone-roles).',
      },
    ],
  },
  {
    category: 'mobile-control',
    slug: 'remove-a-paired-phone',
    title: 'Remove a paired phone',
    summary: 'Revoke a device from the desktop so it can no longer control SelahCue, and what happens on the phone.',
    body: [
      {
        type: 'ol',
        items: [
          'On the desktop, open Settings, Network & Mobile, **Manage devices**.',
          'Find the device in **Paired devices** and press **Revoke**. The button turns into **Confirm?** for a few seconds; press it again to confirm.',
        ],
      },
      {
        type: 'p',
        text: 'Revoking takes effect on that device’s next request. The phone then shows **Access removed** and a **Scan QR to pair again** button, so it can be paired again with a new code.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'Disconnecting on the phone is not the same',
        text: 'The phone’s **Disconnect this device** only clears the details stored on the phone. It does not tell the desktop, so the device stays in the list, and stays trusted, until you revoke it from the desktop.',
      },
      {
        type: 'p',
        text: '**Revoke all** and **Regenerate** appear in Settings but are disabled in this build. Revoke devices one at a time.',
      },
    ],
  },

  // -------------------------------------------------------------- troubleshooting
  {
    category: 'troubleshooting',
    slug: 'after-a-restart-or-crash',
    title: 'SelahCue restarted: what was restored?',
    summary: 'What you should see after a crash or restart, and what to do if the plan will not open.',
    body: [
      {
        type: 'p',
        text: 'SelahCue saves as you work and restores your session automatically when it relaunches. You should see a dismissible **Session restored** notice, with your plan, what was live and staged, blackout, and any running countdown back as they were at the last save (up to five seconds earlier for a countdown).',
      },
      { type: 'h2', text: 'If it says it started clean' },
      {
        type: 'p',
        text: 'If SelahCue was launched three times in 60 seconds without staying up, it starts with a clean session instead. The notice says **Started clean after repeated restarts**. Your previous session is kept, not deleted. Relaunch once the app is stable, and it resumes that session.',
      },
      { type: 'h2', text: 'If the plan will not open' },
      {
        type: 'p',
        text: 'The Service Plan screen may say **Couldn’t open the plan** and offer **Restore last autosave** when a recent autosave exists. Press it, then check the plan: the reply is **Restore requested**, not a confirmation that the restore worked. SelahCue refuses the restore if the plan has changed since the autosave was captured.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'There is no manual choice yet',
        text: 'Settings mentions asking whether to resume or start clean, but this build does not offer that choice. The behaviour above is automatic. Back up, restore and diagnostics export are shown but disabled in Settings.',
      },
      {
        type: 'p',
        text: 'More on what is saved and where: [Working offline and how autosave works](/docs/getting-started/offline-and-autosave).',
      },
    ],
  },
  {
    category: 'troubleshooting',
    slug: 'transcription-will-not-start',
    title: 'Transcription will not start',
    summary: 'The first-time model download, the error messages you may see, and a silent microphone.',
    body: [
      { type: 'h2', text: 'The first time: a model download' },
      {
        type: 'p',
        text: 'Transcription runs on your computer. The speech model is not part of the installer: it is downloaded the first time you press **Start listening**, and that needs an internet connection once. After it finishes, SelahCue works fully offline. Cancelling or an interruption does not resume; start the download again.',
      },
      {
        type: 'p',
        text: 'The size depends on the build: roughly 1.6 GB for a GPU build, about 490 MB for a CPU-only build such as the Windows installer, and about 150 MB for the smallest. The dialog may quote one figure for every build.',
      },
      { type: 'h2', text: 'Messages and what they mean' },
      {
        type: 'ul',
        items: [
          '**You’re offline… Connect to the internet once.** The model has not been downloaded yet and there is no connection.',
          '**Download couldn’t be verified.** The file did not match its expected checksum. Download it again.',
          '**Download interrupted.** The connection dropped. Start the download again.',
          '**This build does not include on-device speech-to-text.** You are running a build made without it.',
          '**On-device STT model not downloaded: transcription unavailable.** Shown by Pre-service Check until the model is downloaded.',
        ],
      },
      { type: 'h2', text: 'No audio reaching the microphone' },
      {
        type: 'p',
        text: 'If the console says **No audio is reaching the microphone**, grant microphone access in System Settings under Privacy & Security, Microphone, then stop and start listening again.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Where the audio goes',
        text: 'Transcription is on-device by default. Cloud transcription is not part of release builds: if cloud is selected in Settings, a release build tells you it does not include it and uses on-device transcription instead.',
      },
    ],
  },
]

export const support: KnowledgeCollection = {
  root: '/support',
  categories: supportCategories,
  articles: supportArticles,
}

export const supportPath = (a: KnowledgeArticle): string => articlePath(support.root, a)
export const findSupportArticle = (category: unknown, slug: unknown) => findArticle(support, category, slug)
export const findSupportCategory = (id: unknown) => findCategory(support, id)
export const supportIn = (categoryId: string) => articlesIn(support, categoryId)
export const supportNeighbours = (a: KnowledgeArticle) => articleNeighbours(support, a)
export const supportRelated = (a: KnowledgeArticle) => relatedIn(support, a)
