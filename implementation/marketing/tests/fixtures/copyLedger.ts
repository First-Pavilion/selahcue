/**
 * THE COPY LEDGER for the seven non-legal secondary pages (ClickUp 17tnw2b2cez, review round 1: Cody M3).
 *
 * `tests/secondaryPages.test.ts` renders each page and fails on ANY rendered text run that is not
 *   1. from the CONTENT LAYER (`src/lib/content`: article, post and category titles and summaries, each already
 *      guarded by `tests/content.test.ts` and its cited sources), or
 *   2. in `newCopy` below: words written in THIS pull request, each reviewed as carrying no promise, or
 *   3. in `preexisting` below: words that were on the page BEFORE this pull request, restyled and not changed in
 *      substance. Many of these are claims the repo does not back (a 24-hour reply, 1,200+ members, versions that
 *      do not exist, three invented roles, a 20% rate). They are NOT this ticket's to remove: owner decision
 *      2026-10-04, ClickUp 17tnw2b0x3h removes them in a branch on top of the four area PRs. They are listed here,
 *      by name, so that (a) none can be ADDED unnoticed, (b) the list can only SHRINK: a test fails when an entry
 *      is no longer rendered, so the claims ticket must delete each entry as it removes the words.
 *
 * Two tests keep `newCopy` honest: it must carry no time, money or earnings promise (a pattern ban), and no entry
 * may be on both lists. A regular expression stands for a computed line (a count, a read time, a date).
 */

export type Entry = string | RegExp

export interface PageLedger {
  /** Written in this pull request. */
  readonly newCopy: readonly Entry[]
  /** Already live before it. Shrink-only: removed by ClickUp 17tnw2b0x3h. */
  readonly preexisting: readonly Entry[]
}

export const LEDGER: Readonly<Record<string, PageLedger>> = {
  Contact: {
    newCopy: [
      'CONTACT',
      "Let's talk",
      'Questions about SelahCue, help with getting set up, or partnering with us. Here is how to get in touch.',
      'Full name',
      'Email',
      'Church / organization',
      'How can we help?',
      'Send message',
    ],
    preexisting: [
      // The form (labels restyled): the title, the required marker and the counter FormField draws.
      'Send us a message',
      '*',
      '0/2000',
      // The three method cards and their links, unbacked and restyled (audit contact-04, 07). The arrow glyph that ended
      // each link text was dropped (Figma draws none); the words are the live ones.
      'Support & Sales Email',
      'Email our dedicated support team directly.',
      'support@selahcue.app',
      'Community & Discord',
      'Join 1,200+ worship tech leaders on Discord for instant help.',
      'Join Discord Community',
      'Enterprise & Multi-Campus',
      'Talk to our church solutions architect for enterprise SLAs.',
      'Schedule a Demo Call',
    ],
  },

  Support: {
    newCopy: ['HELP CENTER', 'How can we help?', 'Guides, answers and troubleshooting for running SelahCue on Sunday.'],
    preexisting: [
      'Start here',
      'Still need help?',
      'Our support team is available to assist your church with technical questions.',
      'Contact Support Team',
      // Computed lines: the article count on a card and the read-time line on a row.
      /^\d+ articles?$/,
      /^[A-Za-z &]+ · \d+ min read$/,
    ],
  },

  Docs: {
    newCopy: [
      'DOCS',
      'GETTING STARTED',
      'GUIDES',
      'REFERENCE',
      'Getting started with SelahCue',
      'SelahCue is a desktop-authoritative, offline-first church presentation app. These guides cover live control, outputs and displays, scripture, timers and service plans, and mobile control.',
      'New here? Start with the basics',
      'Start guide',
    ],
    preexisting: [
      'Documentation',
      'How-to guides for running SelahCue, written from what the app actually does.',
      /^\d+ min read$/,
    ],
  },

  Changelog: {
    newCopy: ['CHANGELOG', "What's new", 'New', 'Improved', 'Fixed'],
    preexisting: [
      'Stay up to date with new features, performance improvements, and bug fixes in SelahCue.',
      // Every release, date, tag and entry: invented, restyled (audit changelog-04, 05). Includes a security claim about an
      // unshipped feature ("Encrypted post-activation downloads for NIV, ESV, and NLT") and a benchmark nobody ran.
      'v1.2.0',
      'August 8, 2026',
      'Latest Release',
      'Native NDI 5 Output Engine',
      'Direct broadcast-quality NDI streaming to OBS, vMix, and Wirecast without extra plugins.',
      'Licensed Bible Entitlement Sync',
      'Encrypted post-activation downloads for NIV, ESV, and NLT translations.',
      'Hardware Decode Optimization',
      'Reduced GPU VRAM usage by 35% on 4K motion backgrounds.',
      'Stage Monitor Timer Overrun',
      'Fixed edge case where stage countdown timer held at 00:00 instead of triggering TIME UP state.',
      'v1.1.0',
      'June 15, 2026',
      'Flutter Mobile Companion App',
      'Pair iOS and Android devices over local Wi-Fi to control slides and stage timers.',
      'Scripture Verse-by-Verse Paging',
      'Faster keyboard navigation using Arrow keys and spacebar.',
      'Display Reconnect Recovery',
      'Restored automatic venue display matching upon HDMI reconnect.',
      'v1.0.0',
      'March 1, 2026',
      'SelahCue Initial Launch',
      'Cross-platform offline presentation software for churches.',
    ],
  },

  Blog: {
    newCopy: [
      'BLOG',
      'The SelahCue blog',
      'Practical notes on running a confident service — reliability, outputs, and the craft of church tech.',
      'Featured',
      // The author line on every card and the featured post: the team, a date and a computed read time.
      /^SelahCue Team · \d{1,2} [A-Z][a-z]{2} \d{4} · \d+ min( read)?$/,
    ],
    preexisting: ['Read', '→', /^: .+$/],
  },

  Careers: {
    newCopy: [
      'CAREERS',
      'Build tools churches rely on',
      'Built to Work Offline',
      'A service cannot be repeated, so slides, scripture and timers run on the desktop with no network.',
      'Open roles',
      "Don't see your role? We're always glad to meet thoughtful people — reach out.",
      // The visually hidden tail that names a role on its Apply button (the role titles themselves are the live ones).
      /^for (Rust Systems & Graphics Engineer|Senior Vue \/ Frontend Engineer|Worship Tech Solutions Specialist)$/,
    ],
    preexisting: [
      // The hero subline and three culture cards, unbacked and restyled (audit careers-08): remote policy, and a usage
      // claim ("thousands of volunteer tech teams") with no data behind it.
      'We are an engineering-driven, remote-first team committed to high-performance, offline-first worship presentation technology.',
      'Fully Remote & Flexible',
      'Work from anywhere in the world with flexible hours built around your life and family.',
      'High Technical Standards',
      'We write Rust, wgpu, and Vue 3 TypeScript. Zero compromise on memory safety, frame latency, or UX quality.',
      'Impact for the Local Church',
      'Your work directly supports thousands of volunteer tech teams and worship leaders every single Sunday.',
      // The three invented roles, their tags (the old single meta line, split) and the Apply buttons (audit careers-07, 09).
      'Rust Systems & Graphics Engineer',
      'Senior Vue / Frontend Engineer',
      'Worship Tech Solutions Specialist',
      'Core Engine',
      'Web & Dashboard',
      'Customer Success',
      'Remote (US/EU/Africa)',
      'Remote',
      'Full-time',
      'Apply Now →',
    ],
  },

  Affiliates: {
    newCopy: [
      'AFFILIATE PROGRAM',
      'Apply now',
      'Affiliate sign in',
      'Affiliate sign in: not available yet',
      'Offline',
      'Slides and timers run offline',
      'How it works',
      'Three steps to get started.',
      '01',
      'Apply to join',
      "Tell us how you'll share SelahCue.",
      '02',
      'Share SelahCue',
      'Recommend it anywhere your audience is.',
      '03',
      'Refer a church',
      'Introduce SelahCue to a church that could use it.',
      'Made for people who talk to churches',
      'Church tech creators',
      'Bloggers, YouTubers and newsletter writers in the worship-tech space.',
      'AV & gear resellers',
      'Sell projectors, mixers and stage gear? Add software your customers need.',
      'Ministry networks',
      'Denominations and multi-site networks recommending tools to member churches.',
      'Consultants & integrators',
      'You set up church production rigs — bundle SelahCue into your builds.',
      "Why it's easy to recommend",
      'Designed so a fault never blanks the live screen',
      'Offline-first: slides, scripture and timers run on the desktop with no network',
      'Affiliate FAQ',
      'Ready to get started?',
      'Apply to join the SelahCue affiliate program.',
      'Not available yet',
    ],
    preexisting: [
      // The programme's figures, rate, window, threshold, payout rails and calculator: NOT-V1, terms undecided (audit
      // affiliates-12 to 14). Restyled; none added.
      'Recommend SelahCue. Earn 20% Recurring Commission.',
      'Help churches upgrade their live worship presentation. Earn passive recurring income on every paid referral for 12 months.',
      '20%',
      'Recurring Commission',
      '60 Days',
      'Cookie Attribution',
      '$50',
      'Low Payout Threshold',
      'Estimate Your Earnings',
      'Slide to see how much you could earn by recommending SelahCue to churches:',
      'Referred Active Churches:',
      /^\d+ churches$/,
      'Monthly Recurring Income',
      /^\$\d+\/mo$/,
      'Estimated Annual Payout',
      /^\$\d+\/yr$/,
      'What is the commission rate?',
      'You earn a 20% recurring commission for 12 months on every paid subscription that signs up using your referral link.',
      'How long does the referral cookie last?',
      'Our referral tracking uses a 60-day last-click attribution window.',
      'When are affiliate payouts made?',
      'Payouts are processed on the 1st of every month via PayPal or Direct Bank Transfer once you reach the $50 minimum threshold.',
      'Who can join the affiliate program?',
      'Worship leaders, tech consultants, Christian bloggers, YouTubers, and church network leaders are welcome to apply!',
    ],
  },
}

/** Words that promise a time, a money outcome or a reply. None may appear in `newCopy`. */
export const PROMISE_PATTERN =
  /\bwithin\b|\bhours?\b|\bdays?\b|\bweeks?\b|\bmonthly\b|\bguarantee|\bfree\b|\bforever\b|for life|%|\$|\bearn|\bcommission|\bincome|\brecurring|\bpayouts?\b|\bpaid\b|\breply|\brespond|\bresponse\b/i
