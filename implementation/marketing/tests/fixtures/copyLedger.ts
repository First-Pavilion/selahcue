/**
 * THE COPY LEDGER for the seven non-legal secondary pages (ClickUp 17tnw2b2cez, review rounds 1 and 2).
 *
 * `tests/secondaryPages.test.ts` renders each page, in its default state AND in the states a visitor reaches by acting (a form
 * submitted with nothing, with bad values and with good ones; a help search with one, several and no results), and fails on ANY
 * piece of copy that is not
 *   1. from the CONTENT LAYER (`src/lib/content`: article, post and category titles and summaries, each already
 *      guarded by `tests/content.test.ts` and its cited sources), or
 *   2. in `newCopy` below: words written in THIS pull request, each reviewed as carrying no promise, or
 *   3. in `unbacked` below: words that were live BEFORE this pull request (or are on a button or line this PR cannot make
 *      true) and CLAIM something the repo does not back: a 24-hour reply, 1,200+ members, versions that do not exist, three
 *      invented roles, a 20% rate, an application that does not exist. They are NOT this ticket's to remove: owner decision
 *      2026-10-04, ClickUp 17tnw2b0x3h removes them in a branch on top of the four area PRs and joins the merge gate. THAT
 *      TICKET'S CHECK IS "`unbacked` is empty" on every page, and its test fails on a line that is no longer rendered, so
 *      the list can only shrink, and each entry has to be deleted by whoever removes the words, or
 *   4. in `harmless` below: everything else that was already there, restyled and not changed in substance (a heading, a
 *      count, a validation message, an accessible name). It claims nothing; a test fails on a promise word in it, so a claim
 *      cannot hide in this list.
 *
 * WHAT THE LEDGER SEES: every text run, and the value of every `title`, `alt`, `aria-label`, `aria-description`,
 * `aria-roledescription`, `aria-valuetext` and `placeholder` attribute, in each state listed in the test; and a `content:`
 * declaration in the scoped styles of every view and every component this ticket owns (anything but an empty string fails).
 *
 * WHAT IT DOES NOT SEE (so nobody reads a green ledger as more than it is): copy a state not listed in the test would show
 * (the Contact success card after a REAL send, which does not exist yet; the Docs and Blog pages' own hash states);
 * copy that only a script writes after load; the document title and meta description, which the router and the head code
 * set outside these views; text inside the content layer (it is accepted by name, and guarded by `tests/content.test.ts`);
 * text in the shared components themselves (UiButton, FormField, FaqAccordion, the footer: other tickets), except where they
 * render it here; text in an image; and CSS `content` in files outside the ones listed. It reads what is WRITTEN, and does
 * not say any line is true.
 *
 * Tests keep the ledger honest: `newCopy` and `harmless` carry no time, money, earnings or reply word (a pattern ban); no entry
 * is on two lists; every entry is still rendered; and the named claims the reviewers listed are on `unbacked`. A regular
 * expression stands for a computed line (a count, a read time, a date, a typed name).
 */

export type Entry = string | RegExp

export interface PageLedger {
  /** Written in this pull request. */
  readonly newCopy: readonly Entry[]
  /** Claims the repo does not back (or an affordance that does not work). ClickUp 17tnw2b0x3h removes them: "empty" is its check. */
  readonly unbacked: readonly Entry[]
  /** Already live, restyled, claiming nothing. */
  readonly harmless: readonly Entry[]
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
      // The form's accessible name and its placeholders (the frame's words, contact-09, contact-12).
      'Contact us',
      'Jane Pastor',
      'jane@yourchurch.org',
      'Tell us a little about what you need…',
      // The two length rules this PR added to the form (contact-12).
      'Name must be 100 characters or fewer',
      'Church / organization must be 100 characters or fewer',
      // ClickUp 17tnw2b0x3h: the form sends nothing (no endpoint yet), so the page says so and names the one address the owner
      // confirmed (2026-10-04). No reply time, no person, no channel that does not exist.
      'The contact form is not available yet. Please email us instead.',
      'Email us',
      'Write to us at this address.',
      'support@selahcueapp.com',
    ],
    // Empty on purpose: the claims that were here (a 24-hour reply, "Message Received!", 1,200+ Discord members, two links that
    // went nowhere, "enterprise SLAs", a "dedicated support team") were removed by ClickUp 17tnw2b0x3h and are banned in NAMED_CLAIMS.
    unbacked: [],
    harmless: [
      'Send us a message',
      '*',
      '0/2000',
      'Grace Community Church',
      // The form's own validation messages from before this PR.
      'Name is required',
      'Email is required',
      'Message is required',
      'Please enter a valid email address',
    ],
  },

  Support: {
    newCopy: [
      'HELP CENTER',
      'How can we help?',
      'Guides, answers and troubleshooting for running SelahCue on Sunday.',
      'Search help articles…',
      // ClickUp 17tnw2b0x3h: replaces "Our support team is available to assist your church" (a staffing claim, audit support-08).
      "Can't find what you need? Get in touch.",
    ],
    unbacked: [],
    harmless: [
      'Start here',
      'Still need help?',
      'Contact Support Team',
      'Search help articles',
      // The search's heading and its status lines (read out by a screen reader and shown above the results).
      'Search results',
      'No help articles match that search.',
      /^\d+ help articles? match(?:es)? your search\.$/,
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
    // The Docs page's own lines claim nothing; what is unbacked here lives in the content layer (docs-04, 05, 06, 09).
    unbacked: [],
    harmless: [
      'Documentation',
      'How-to guides for running SelahCue, written from what the app actually does.',
      'Documentation topics',
      /^\d+ min read$/,
    ],
  },

  Changelog: {
    // The group labels ("New", "Improved", "Fixed") are drawn only when a release exists; they are not rendered today, so they
    // are not listed. The first release adds them, with its entries, in the same change.
    newCopy: [
      'CHANGELOG',
      "What's new",
      // ClickUp 17tnw2b0x3h: the empty state that replaced three invented releases.
      'No release notes yet',
      'New features, improvements and fixes will be listed here with each release.',
    ],
    // Empty on purpose: v1.2.0 "Latest Release", v1.1.0, v1.0.0, their dates and every entry (an NDI engine, encrypted licensed
    // downloads, a GPU benchmark) were invented and removed by ClickUp 17tnw2b0x3h; they are banned in NAMED_CLAIMS.
    unbacked: [],
    harmless: ['Stay up to date with new features, performance improvements, and bug fixes in SelahCue.'],
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
    unbacked: [],
    harmless: ['Read', '→', /^: .+$/],
  },

  Careers: {
    // Only what renders with no role open. The role rows, their tags, the Apply buttons and the "Don't see your role?" line are
    // drawn only when a role exists; the first real role adds them to the ledger in the same change.
    newCopy: [
      'CAREERS',
      'Build tools churches rely on',
      // ClickUp 17tnw2b0x3h: the hero line now says only what the product is (it was a remote-first company claim), and the roles
      // band says plainly that nothing is open.
      'SelahCue is offline-first presentation software for churches.',
      'Open roles',
      'There are no open roles right now.',
    ],
    // Empty on purpose: the remote-first line, the three culture cards ("thousands of volunteer tech teams"), the three invented
    // roles with their tags and Apply buttons were removed by ClickUp 17tnw2b0x3h; they are banned in NAMED_CLAIMS.
    unbacked: [],
    harmless: [],
  },

  Affiliates: {
    newCopy: [
      'AFFILIATE PROGRAM',
      'Affiliate sign in',
      'Affiliate sign in: not available yet',
      'Offline',
      'Slides and timers run offline',
      'How it works',
      'Three steps to get started.',
      '01',
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
      'Not available yet',
    ],
    unbacked: [
      // The page tells two stories about Apply (review round 2, Quinn Q5, Cody N4): the hero "Apply now" opens the Contact form,
      // which sends nothing; the band's button is disabled ("Not available yet"); step 01 and the band's line describe an
      // application that does not exist. Words this PR wrote, listed here because the claims ticket must settle them.
      'Apply now',
      'Apply to join',
      "Tell us how you'll share SelahCue.",
      'Apply to join the SelahCue affiliate program.',
      // The programme's figures, rate, window, threshold, payout rails and calculator: NOT-V1, terms undecided (audit
      // affiliates-10, 12 to 15). Restyled; none added.
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
    harmless: [],
  },
}

/**
 * Words that promise a time, a money outcome, a reply or a privacy guarantee. None may appear in `newCopy` or `harmless`.
 * Plural "answers" is not here on purpose: "Guides, answers and troubleshooting" names content, where "We answer every message"
 * promises a reply.
 */
export const PROMISE_PATTERN =
  /\bwithin\b|\bhours?\b|\bdays?\b|\bweeks?\b|\bmonthly\b|\bguarantee|\bfree\b|\bforever\b|for life|%|\$|\bearn|\bcommission|\bincome|\brecurring|\bpayouts?\b|\bpaid\b|\breply|\brespond|\bresponse\b|\banswer(?:ed|ing)?\b|\balways\b|\binstant|\bimmediate|\bnever\s+(?:share|sell|send|store|collect|track)/i

/**
 * The claims the reviewers named, as a sample run each. A test requires each to be matched by `unbacked` of its page, so that
 * moving one of them to `harmless` (where the claims ticket would never look) fails.
 */
export const NAMED_CLAIMS: ReadonlyArray<readonly [page: string, sample: string]> = [
  ['Contact', 'Thank you for reaching out, Ana. A SelahCue specialist will respond within 24 hours.'],
  ['Contact', 'Message Received!'],
  ['Contact', 'Join 1,200+ worship tech leaders on Discord for instant help.'],
  ['Contact', 'Join Discord Community'],
  ['Contact', 'Schedule a Demo Call'],
  ['Support', 'Our support team is available to assist your church with technical questions.'],
  ['Changelog', 'v1.2.0'],
  ['Changelog', 'Latest Release'],
  ['Changelog', 'Encrypted post-activation downloads for NIV, ESV, and NLT translations.'],
  ['Careers', 'Rust Systems & Graphics Engineer'],
  ['Careers', 'Senior Vue / Frontend Engineer'],
  ['Careers', 'Worship Tech Solutions Specialist'],
  ['Careers', 'Apply Now →'],
  ['Careers', 'Your work directly supports thousands of volunteer tech teams and worship leaders every single Sunday.'],
  ['Affiliates', 'Recommend SelahCue. Earn 20% Recurring Commission.'],
  ['Affiliates', '60 Days'],
  ['Affiliates', '$50'],
  ['Affiliates', 'Estimate Your Earnings'],
  ['Affiliates', 'Payouts are processed on the 1st of every month via PayPal or Direct Bank Transfer once you reach the $50 minimum threshold.'],
  ['Affiliates', 'Apply now'],
  ['Affiliates', 'Apply to join'],
  ['Affiliates', 'Apply to join the SelahCue affiliate program.'],
]
