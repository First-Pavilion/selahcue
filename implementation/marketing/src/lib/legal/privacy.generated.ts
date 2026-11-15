/**
 * GENERATED FILE. DO NOT EDIT BY HAND.
 * Source of truth: docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md
 * Regenerate:      npm run sync:legal (in implementation/marketing)
 *
 * `tests/legal.test.ts` regenerates this in memory and fails if it differs from the
 * committed text, so the page can never drift from the markdown drafts.
 */
import type { LegalDocument } from './types.ts'

export const privacyPolicy: LegalDocument = {
  "source": "docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md",
  "title": "SelahCue Privacy Policy",
  "banner": {
    "headline": [
      {
        "kind": "strong",
        "children": [
          { "kind": "text", "text": "DRAFT — NOT LEGAL ADVICE — REQUIRES REVIEW BY A QUALIFIED LAWYER BEFORE PUBLICATION" }
        ]
      }
    ],
    "notes": [
      {
        "kind": "paragraph",
        "inline": [
          { "kind": "text", "text": "Version 0.4 (draft, 2026-11-15). Status: Draft — every " },
          { "kind": "placeholder", "name": "PLACEHOLDER" },
          { "kind": "text", "text": " must be filled and every launch-readiness condition in " },
          { "kind": "code", "text": "docs/legal/LEGAL-DRAFT-NOTES.md" },
          { "kind": "text", "text": " §4 must be satisfied before publication. This draft describes the planned Free desktop release. The operational checks required before publication are recorded in the launch-readiness notes." }
        ]
      }
    ]
  },
  "version": { "number": "0.4", "status": "draft", "date": "2026-11-15", "line": "Version 0.4 (draft, 2026-11-15)", "source": "banner" },
  "facts": [
    {
      "inline": [
        { "kind": "strong", "children": [{ "kind": "text", "text": "Who we are:" }] },
        { "kind": "text", "text": " First Pavilion Technologies, trading as SelahCue (\"SelahCue\", \"we\", \"us\")" }
      ],
      "children": []
    },
    {
      "inline": [
        { "kind": "strong", "children": [{ "kind": "text", "text": "Registered address:" }] },
        { "kind": "text", "text": " 4, Law Castle, Taiwo Street, Omida, Abeokuta, Ogun State, Nigeria" }
      ],
      "children": []
    },
    {
      "inline": [
        { "kind": "strong", "children": [{ "kind": "text", "text": "Registration number:" }] },
        { "kind": "text", "text": " 1557879" }
      ],
      "children": []
    },
    {
      "inline": [
        { "kind": "strong", "children": [{ "kind": "text", "text": "Privacy contact:" }] },
        { "kind": "text", "text": " " },
        { "kind": "code", "text": "support@selahcueapp.com" }
      ],
      "children": []
    },
    {
      "inline": [
        { "kind": "strong", "children": [{ "kind": "text", "text": "Effective date:" }] },
        { "kind": "text", "text": " October 31, 2026" }
      ],
      "children": []
    }
  ],
  "summary": {
    "id": "summary",
    "number": null,
    "title": "Summary in plain language",
    "level": 2,
    "blocks": [
      {
        "kind": "paragraph",
        "inline": [
          { "kind": "text", "text": "This summary is part of the policy. The full sections below give the detail." }
        ]
      },
      {
        "kind": "list",
        "items": [
          {
            "inline": [
              {
                "kind": "strong",
                "children": [
                  { "kind": "text", "text": "Your church's content is stored on your church's computers." }
                ]
              },
              { "kind": "text", "text": " This includes slides, songs, scripture, service plans, sermon transcripts and sermon notes. Section " },
              { "kind": "ref", "anchor": "s-3", "text": "3" },
              { "kind": "text", "text": " explains what leaves those computers when you request a cloud feature or send us content for support." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Local transcription runs on your computer." }]
              },
              { "kind": "text", "text": " The first time you use it, the app may need to download a speech-recognition model from Hugging Face." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Cloud features require opt-in." }]
              },
              { "kind": "text", "text": " Cloud transcription streams audio directly to Deepgram. For a notes request, the app sends the selected transcript text to SelahCue for temporary processing with OpenAI. This processing can happen outside your country." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Your SelahCue account" }]
              },
              { "kind": "text", "text": " holds your email address, a one-way password hash, your church or organisation name, your country and time zone, and your name if you give it." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Licences, devices and downloads." }]
              },
              { "kind": "text", "text": " Activation registers your device with your account. When installers are published, you can download them without signing in." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Website cookies and storage" }]
              },
              { "kind": "text", "text": " support sign-in and security. The website loads a font from Google, so Google receives your IP address when your browser requests it." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [
                  { "kind": "text", "text": "We do not sell your personal data, and we do not show ads." }
                ]
              }
            ],
            "children": []
          },
          {
            "inline": [
              { "kind": "strong", "children": [{ "kind": "text", "text": "Privacy requests." }] },
              { "kind": "text", "text": " Contact us at " },
              { "kind": "code", "text": "support@selahcueapp.com" },
              { "kind": "text", "text": " (see section " },
              { "kind": "ref", "anchor": "s-11", "text": "11" },
              { "kind": "text", "text": ")." }
            ],
            "children": []
          }
        ]
      }
    ],
    "children": []
  },
  "parts": [
    {
      "label": null,
      "title": null,
      "sections": [
        {
          "id": "s-1",
          "number": "1",
          "title": "Who this policy covers",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "This policy explains how First Pavilion Technologies, trading as SelahCue, handles personal data when you:" }
              ],
              "clause": "1.1",
              "anchor": "s-1-1"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    { "kind": "text", "text": "visit our website at " },
                    { "kind": "code", "text": "https://selahcueapp.com" },
                    { "kind": "text", "text": ";" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "create or use a SelahCue account, including signing in, verifying your email and resetting your password;" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "activate SelahCue on a computer, or download the desktop software;" }
                  ],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "use SelahCue's optional cloud features;" }],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "install and use the SelahCue desktop app; or" }],
                  "children": []
                },
                { "inline": [{ "kind": "text", "text": "contact us for help." }], "children": [] }
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "We decide why and how the personal data described in section " },
                { "kind": "ref", "anchor": "s-3", "text": "3" },
                { "kind": "text", "text": " is used. The exception is audio and transcript text you send to SelahCue for a sermon-note draft. We process it to provide the requested feature to your church. Cloud transcription audio goes from your device directly to Deepgram (see section " },
                { "kind": "ref", "anchor": "s-3-8", "text": "3.8" },
                { "kind": "text", "text": ")." }
              ],
              "clause": "1.2",
              "anchor": "s-1-2"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "This policy does " },
                { "kind": "strong", "children": [{ "kind": "text", "text": "not" }] },
                { "kind": "text", "text": " cover:" }
              ],
              "clause": "1.3",
              "anchor": "s-1-3"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    { "kind": "text", "text": "content your church creates and keeps on its own computers with SelahCue (see section " },
                    { "kind": "ref", "anchor": "s-2", "text": "2" },
                    { "kind": "text", "text": ");" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "the separately documented SelahCue Controller app; or" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "other organisations' websites or services, even if we link to them." }
                  ],
                  "children": []
                }
              ]
            }
          ],
          "children": []
        },
        {
          "id": "s-2",
          "number": "2",
          "title": "Data that stays with your church",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "SelahCue is built to work offline. The desktop app stores your church's working data on the computer where it runs. This includes:" }
              ],
              "clause": "2.1",
              "anchor": "s-2-1"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    { "kind": "text", "text": "service plans, slides, slide decks, songs, themes and screen settings;" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "references to your media files (the files stay where you keep them);" }
                  ],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "scripture you search for and display;" }],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "transcripts made by live transcription, including corrections and detected scripture references; and" }
                  ],
                  "children": []
                },
                { "inline": [{ "kind": "text", "text": "sermon-note drafts." }], "children": [] }
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "Your church controls what it creates and keeps on its computers, who can access it and how long it stays there. Sections " },
                { "kind": "ref", "anchor": "s-2-6", "text": "2.6" },
                { "kind": "text", "text": " and " },
                { "kind": "ref", "anchor": "s-3-8", "text": "3.8" },
                { "kind": "text", "text": " explain what happens if you send us content." }
              ],
              "clause": "2.2",
              "anchor": "s-2-2"
            },
            {
              "kind": "paragraph",
              "inline": [
                {
                  "kind": "strong",
                  "children": [
                    { "kind": "text", "text": "Transcripts can contain personal data about other people." }
                  ]
                },
                { "kind": "text", "text": " Live transcription captures whatever the selected microphone hears. That can include the words of preachers, worship leaders, congregation members and children. Sermon content may reveal people's religious beliefs. Before you use live transcription, your church should:" }
              ],
              "clause": "2.3",
              "anchor": "s-2-3"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    { "kind": "text", "text": "tell people that services may be transcribed (the desktop app includes a notice you can display for this);" }
                  ],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "decide how long transcripts are kept; and" }],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "limit who can access the computers that hold them." }],
                  "children": []
                }
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                {
                  "kind": "strong",
                  "children": [
                    { "kind": "text", "text": "How the desktop app protects and manages this data." }
                  ]
                }
              ],
              "clause": "2.4",
              "anchor": "s-2-4"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    { "kind": "text", "text": "The database that holds transcripts is encrypted on disk by default. The encryption key is kept in your operating system's secure credential store, or is derived from a passphrase on systems that do not have one." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "Some other local files are " },
                    { "kind": "strong", "children": [{ "kind": "text", "text": "not" }] },
                    { "kind": "text", "text": " encrypted by the app, including the slide-deck library and your media files. Protect access to the computer itself." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "Transcripts stay on the computer until they are deleted. An operator can delete a transcript in the operator console, and an administrator can set the app to delete transcripts automatically after a chosen number of days. Deleting a transcript also deletes its corrections and detected scripture references, and, by default, the sermon-note draft made from it." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "The desktop app does not keep audio recordings. It converts speech to text and keeps the text." }
                  ],
                  "children": []
                }
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                {
                  "kind": "strong",
                  "children": [{ "kind": "text", "text": "Local network features." }]
                },
                { "kind": "text", "text": " Where enabled, discovery advertises the desktop app on your church's local network. NDI output sends presentation video to other equipment on that network. These local connections do not send your presentation content to SelahCue." }
              ],
              "clause": "2.5",
              "anchor": "s-2-5"
            },
            {
              "kind": "paragraph",
              "inline": [
                {
                  "kind": "strong",
                  "children": [{ "kind": "text", "text": "If you share church data with us." }]
                },
                { "kind": "text", "text": " If you send us a transcript, screenshot or file, for example to get help, we handle it as described in section " },
                { "kind": "ref", "anchor": "s-3-6", "text": "3.6" },
                { "kind": "text", "text": ". Cloud features are described in section " },
                { "kind": "ref", "anchor": "s-3-8", "text": "3.8" },
                { "kind": "text", "text": "." }
              ],
              "clause": "2.6",
              "anchor": "s-2-6"
            }
          ],
          "children": []
        },
        {
          "id": "s-3",
          "number": "3",
          "title": "Personal data we collect and why",
          "level": 2,
          "blocks": [],
          "children": [
            {
              "id": "s-3-1",
              "number": "3.1",
              "title": "Your SelahCue account",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "You need an account to activate SelahCue on your computers, manage devices and use optional cloud features. See section " },
                    { "kind": "ref", "anchor": "s-3-3", "text": "3.3" },
                    { "kind": "text", "text": " for public desktop downloads." }
                  ]
                },
                {
                  "kind": "table",
                  "header": [
                    [{ "kind": "text", "text": "What we collect" }],
                    [{ "kind": "text", "text": "Where it comes from" }],
                    [{ "kind": "text", "text": "Why we use it" }],
                    [{ "kind": "text", "text": "Our reason" }]
                  ],
                  "rows": [
                    [
                      [{ "kind": "text", "text": "Email address" }],
                      [{ "kind": "text", "text": "You, at sign-up" }],
                      [
                        { "kind": "text", "text": "To create your account, sign you in and send account emails" }
                      ],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [{ "kind": "text", "text": "Password" }],
                      [{ "kind": "text", "text": "You, at sign-up or reset" }],
                      [
                        { "kind": "text", "text": "To sign you in. We store only a salted one-way hash, never the password itself" }
                      ],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [{ "kind": "text", "text": "Church or organisation name" }],
                      [{ "kind": "text", "text": "You, at sign-up" }],
                      [{ "kind": "text", "text": "To set up your organisation's account" }],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [{ "kind": "text", "text": "Country" }],
                      [
                        { "kind": "text", "text": "You, at sign-up (the form suggests one from your browser settings)" }
                      ],
                      [{ "kind": "text", "text": "To set up your account" }],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [{ "kind": "text", "text": "Time zone" }],
                      [{ "kind": "text", "text": "Your browser, automatically at sign-up" }],
                      [
                        { "kind": "text", "text": "To show dates and times correctly and to time account events and allowance periods" }
                      ],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [{ "kind": "text", "text": "Your name (optional)" }],
                      [{ "kind": "text", "text": "You, at sign-up" }],
                      [
                        { "kind": "text", "text": "To address you and show who manages the account" }
                      ],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [
                        { "kind": "text", "text": "Account role (administrator or member) and status" }
                      ],
                      [{ "kind": "text", "text": "Created by our system" }],
                      [{ "kind": "text", "text": "To control who can manage licences and devices" }],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [{ "kind": "text", "text": "Email-verification status and time" }],
                      [{ "kind": "text", "text": "Created by our system" }],
                      [{ "kind": "text", "text": "To confirm you control the email address" }],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [
                        { "kind": "text", "text": "Sign-in sessions (a masked identifier, issue, expiry and last-used times)" }
                      ],
                      [{ "kind": "text", "text": "Created by our system" }],
                      [
                        { "kind": "text", "text": "To keep you signed in and let you sign out everywhere" }
                      ],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [{ "kind": "text", "text": "Failed sign-in count and temporary lock time" }],
                      [{ "kind": "text", "text": "Created by our system" }],
                      [{ "kind": "text", "text": "To protect your account from password guessing" }],
                      [{ "kind": "text", "text": "To keep our services secure" }]
                    ],
                    [
                      [
                        { "kind": "text", "text": "Notes our staff record about your account, and licence details" }
                      ],
                      [{ "kind": "text", "text": "Our staff and our system" }],
                      [{ "kind": "text", "text": "To support you and manage your licence" }],
                      [{ "kind": "text", "text": "To provide the service; to run our business" }]
                    ]
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "Because SelahCue is made for churches, holding an account may suggest a religious affiliation. We use account details only to provide the service. We do not use them to profile anyone's beliefs." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-2",
              "number": "3.2",
              "title": "Emails we send you",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "These emails help you set up and recover your account:" }
                  ]
                },
                {
                  "kind": "list",
                  "items": [
                    {
                      "inline": [
                        { "kind": "text", "text": "an email-verification link, which expires after 24 hours;" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        { "kind": "text", "text": "a password-reset link, which expires after 1 hour;" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        { "kind": "text", "text": "a notice if someone tries to create an account with your email address. We send this instead of telling the person signing up that the address is already registered." }
                      ],
                      "children": []
                    }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "We use an email delivery provider to send these messages: " },
                    { "kind": "placeholder", "name": "TRANSACTIONAL_EMAIL_PROVIDER" },
                    { "kind": "text", "text": "." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "We send marketing emails only to people who have agreed to receive them, and you can withdraw that consent at any time using the link in each email or by contacting us." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-3",
              "number": "3.3",
              "title": "Licences, devices and downloads",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Activation." }] },
                    { "kind": "text", "text": " When you activate the desktop app on a computer, the app sends us:" }
                  ]
                },
                {
                  "kind": "list",
                  "items": [
                    {
                      "inline": [
                        { "kind": "text", "text": "a device identifier generated by the app (a random identifier the app creates for the computer);" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [{ "kind": "text", "text": "the platform (for example, Windows or macOS);" }],
                      "children": []
                    },
                    {
                      "inline": [{ "kind": "text", "text": "the app version; and" }],
                      "children": []
                    },
                    {
                      "inline": [
                        { "kind": "text", "text": "a device name, if you choose one (for example, \"Sound booth PC\")." }
                      ],
                      "children": []
                    }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "We record which licence the device uses, when it was activated and its status. We send back a device credential, which the app keeps in your operating system's secure credential store, and a signed licence file, which the app keeps so it can run offline until the licence period ends." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Licence check-ins." }]
                    },
                    { "kind": "text", "text": " When an activated device is online, the app contacts us from time to time, using its device credential, to refresh its licence file. We record when each device last checked in." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Downloads." }] },
                    { "kind": "text", "text": " When installers are published, you can download them without an account or an activated device. The public installer files use immutable release paths in DigitalOcean Spaces in SFO3 (San Francisco). Your browser connects directly to that service, which receives your IP address and standard request information. The public links use no SelahCue account or device credential." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "We use activation and check-in information to apply device limits and usage allowances, manage devices and prevent misuse of licences. Activation and check-ins do not send us slides, transcripts or audio." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "If your organisation uses an enrolment key to activate, we store the key in hashed form, with a short masked version for recognition." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-4",
              "number": "3.4",
              "title": "Free service",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "This release offers ongoing Free access. It has no paid checkout, and we do not ask for payment details when you sign up, activate a device or download a public installer." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-5",
              "number": "3.5",
              "title": "Website visits, security and server records",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "When you use our website or online services, we and our hosting providers process technical information such as your IP address, browser type and requests. We use it to deliver the service, keep it secure and fix problems." }
                  ]
                },
                {
                  "kind": "list",
                  "items": [
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "Rate limiting." }]
                        },
                        { "kind": "text", "text": " We use short-lived counters to limit repeated requests, such as password resets." }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "Operational logs." }]
                        },
                        { "kind": "text", "text": " See section " },
                        { "kind": "ref", "anchor": "s-8", "text": "8" },
                        { "kind": "text", "text": " for retention." }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "Security and audit records." }]
                        },
                        { "kind": "text", "text": " We record important account, licence and cloud-feature actions such as sign-up, device activation and cloud access decisions. These records can include an internal identifier, the action, its outcome and the time. Cloud usage records are described in section " },
                        { "kind": "ref", "anchor": "s-3-8", "text": "3.8" },
                        { "kind": "text", "text": "." }
                      ],
                      "children": []
                    }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-6",
              "number": "3.6",
              "title": "Support and contact",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "When you email us at " },
                    { "kind": "code", "text": "support@selahcueapp.com" },
                    { "kind": "text", "text": ", we use your contact details, message and any attachments to deal with your request and improve our support. Please avoid sending transcripts or other church content unless we need it to help you." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-7",
              "number": "3.7",
              "title": "The desktop app's internet connections",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "The desktop app does not include advertising, analytics, telemetry or crash-reporting tools. It uses your microphone or audio input only when an operator starts live transcription." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [{ "kind": "text", "text": "The desktop app connects to the internet only to:" }]
                },
                {
                  "kind": "list",
                  "items": [
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "activate and check in" }]
                        },
                        { "kind": "text", "text": ", as described in section " },
                        { "kind": "ref", "anchor": "s-3-3", "text": "3.3" },
                        { "kind": "text", "text": ";" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "use cloud features" }]
                        },
                        { "kind": "text", "text": " that an administrator has turned on, as described in section " },
                        { "kind": "ref", "anchor": "s-3-8", "text": "3.8" },
                        { "kind": "text", "text": ";" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "download the speech-recognition model." }]
                        },
                        { "kind": "text", "text": " The first time you use live transcription, the app downloads a model file from Hugging Face (" },
                        { "kind": "code", "text": "huggingface.co" },
                        { "kind": "text", "text": "). Your computer's IP address and a standard web request go to Hugging Face, as with any download. The app checks the file has not been altered before using it. Hugging Face handles that request under its own privacy policy." }
                      ],
                      "children": []
                    }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-8",
              "number": "3.8",
              "title": "Optional cloud features",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "This Free release is designed to provide two optional cloud features:" }
                  ]
                },
                {
                  "kind": "list",
                  "items": [
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "Cloud transcription." }]
                        },
                        { "kind": "text", "text": " After an administrator opts in and an operator starts cloud transcription, the desktop app streams live audio directly to Deepgram using a short-lived access credential. Deepgram returns text to the app. SelahCue does not receive the audio." }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "AI sermon notes." }]
                        },
                        { "kind": "text", "text": " When an operator requests a draft, the desktop app sends the selected transcript text to SelahCue. A SelahCue server worker uses a server-held OpenAI credential to process the text with OpenAI and stage the draft for the desktop app to retrieve. The notes request contains transcript text rather than audio." }
                      ],
                      "children": []
                    }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "The features are off by default and an administrator opts in to each separately. The app explains what it sends, who receives it and that processing can occur abroad. The app shows when cloud transcription is active." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Temporary staging for notes." }]
                    },
                    { "kind": "text", "text": " The intended limit for keeping source text in temporary storage is 5 minutes. The staged draft is retrievable for up to 15 minutes from staging. The desktop app validates the draft and acknowledges receipt after it durably saves it locally. Acknowledgement triggers deletion of the staged copy. The intended physical limit for the staged draft is 20 minutes from staging if cleanup fails. The design excludes source text and drafts from the account database, job broker, logs, traces and backups." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Provider retention." }]
                    },
                    { "kind": "text", "text": " The temporary staging limits apply to SelahCue's storage. Deepgram's handling of audio and OpenAI's handling of transcript text and responses are separate. " },
                    { "kind": "placeholder", "name": "CLOUD_PROVIDER_RETENTION_AND_USE" }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Usage records." }] },
                    { "kind": "text", "text": " We use records such as organisation and request identifiers, timestamps, outcomes and usage units to administer weekly allowances and investigate errors or misuse. These records exclude audio, transcript text and generated drafts." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-9",
              "number": "3.9",
              "title": "Bible texts",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "Bundled Bible texts can be used locally. The installer storage described in section " },
                    { "kind": "ref", "anchor": "s-3-3", "text": "3.3" },
                    { "kind": "text", "text": " is for the desktop software." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-10",
              "number": "3.10",
              "title": "What we do not do",
              "level": 3,
              "blocks": [
                {
                  "kind": "list",
                  "items": [
                    {
                      "inline": [{ "kind": "text", "text": "We do not sell personal data." }],
                      "children": []
                    },
                    {
                      "inline": [
                        { "kind": "text", "text": "We do not share personal data for targeted or cross-context behavioural advertising." }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        { "kind": "text", "text": "We do not make decisions about you based solely on automated processing that have legal or similarly significant effects. Applying plan limits and usage allowances is automatic, but it only controls access to features you have chosen, and you can contact us about any decision." }
                      ],
                      "children": []
                    }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-11",
              "number": "3.11",
              "title": "The SelahCue Controller mobile app",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "The SelahCue Controller has a separate privacy policy in " },
                    { "kind": "code", "text": "docs/legal/PRIVACY.md" },
                    { "kind": "text", "text": ". This policy covers the desktop and website release." }
                  ]
                }
              ],
              "children": []
            }
          ]
        },
        {
          "id": "s-4",
          "number": "4",
          "title": "Cookies and similar technologies",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [{ "kind": "text", "text": "Our website uses only these technologies:" }],
              "clause": "4.1",
              "anchor": "s-4-1"
            },
            {
              "kind": "table",
              "header": [
                [{ "kind": "text", "text": "Name" }],
                [{ "kind": "text", "text": "Type" }],
                [{ "kind": "text", "text": "Purpose" }],
                [{ "kind": "text", "text": "How long" }]
              ],
              "rows": [
                [
                  [{ "kind": "code", "text": "selahcue_account_session" }],
                  [
                    { "kind": "text", "text": "Cookie (secure, not readable by page scripts, sent only to our own site)" }
                  ],
                  [{ "kind": "text", "text": "Keeps you signed in" }],
                  [{ "kind": "text", "text": "Until you sign out, or up to 30 days" }]
                ],
                [
                  [{ "kind": "code", "text": "csrftoken" }],
                  [{ "kind": "text", "text": "Cookie" }],
                  [
                    { "kind": "text", "text": "Protects our forms against cross-site request forgery" }
                  ],
                  [{ "kind": "text", "text": "Up to 1 year" }]
                ],
                [
                  [{ "kind": "code", "text": "selahcue.session" }],
                  [{ "kind": "text", "text": "Browser local storage" }],
                  [
                    { "kind": "text", "text": "Remembers your account role, organisation reference and session expiry, so the page can show that you are signed in. It contains no password or session credential" }
                  ],
                  [
                    { "kind": "text", "text": "Removed when you sign out, or ignored once the session has expired" }
                  ]
                ]
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "Our own cookies and storage are strictly necessary for signing in and security, so we do not ask for consent to use them. You can block them in your browser settings, but you will not be able to sign in." }
              ],
              "clause": "4.2",
              "anchor": "s-4-2"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "strong", "children": [{ "kind": "text", "text": "Google Fonts." }] },
                { "kind": "text", "text": " Our website loads the Inter font from Google's servers (" },
                { "kind": "code", "text": "fonts.googleapis.com" },
                { "kind": "text", "text": " and " },
                { "kind": "code", "text": "fonts.gstatic.com" },
                { "kind": "text", "text": "). When it does, your browser sends your IP address and standard browser information to Google. Google handles that data under its own privacy policy." }
              ],
              "clause": "4.3",
              "anchor": "s-4-3"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "We do not use analytics, advertising or social-media tracking cookies or pixels." }
              ],
              "clause": "4.4",
              "anchor": "s-4-4"
            }
          ],
          "children": []
        },
        {
          "id": "s-5",
          "number": "5",
          "title": "Our reasons for using personal data",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "We use personal data only where we have a good reason that the law recognises:" }
              ],
              "clause": "5.1",
              "anchor": "s-5-1"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "To provide the service" }]
                    },
                    { "kind": "text", "text": " you asked for, including your account, plan, licences, downloads and cloud features." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "To meet legal requirements" }]
                    },
                    { "kind": "text", "text": ", such as keeping tax and accounting records and responding to lawful requests." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [
                        { "kind": "text", "text": "To keep our services secure and run our business" }
                      ]
                    },
                    { "kind": "text", "text": ", such as preventing fraud and abuse, where this does not override your rights." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "With your consent" }]
                    },
                    { "kind": "text", "text": ", where we ask for it, such as for marketing emails. You can withdraw consent at any time. Withdrawing does not affect anything we did before." }
                  ],
                  "children": []
                }
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "We need the information marked as required at sign-up to create your account." }
              ],
              "clause": "5.2",
              "anchor": "s-5-2"
            }
          ],
          "children": []
        },
        {
          "id": "s-6",
          "number": "6",
          "title": "Who we share personal data with",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [{ "kind": "text", "text": "Recipients include:" }],
              "clause": "6.1",
              "anchor": "s-6-1"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Hosting and infrastructure providers" }]
                    },
                    { "kind": "text", "text": " that operate the website and account services (section " },
                    { "kind": "ref", "anchor": "s-7", "text": "7" },
                    { "kind": "text", "text": ")." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "DigitalOcean Spaces" }]
                    },
                    { "kind": "text", "text": ", which receives public installer requests (section " },
                    { "kind": "ref", "anchor": "s-3-3", "text": "3.3" },
                    { "kind": "text", "text": ")." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Our email delivery provider" }]
                    },
                    { "kind": "text", "text": ", which sends account emails (section " },
                    { "kind": "ref", "anchor": "s-3-2", "text": "3.2" },
                    { "kind": "text", "text": ")." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Deepgram" }] },
                    { "kind": "text", "text": ", which receives audio from your device for cloud transcription, and " },
                    { "kind": "strong", "children": [{ "kind": "text", "text": "OpenAI" }] },
                    { "kind": "text", "text": ", which processes transcript text for requested sermon notes (section " },
                    { "kind": "ref", "anchor": "s-3-8", "text": "3.8" },
                    { "kind": "text", "text": ")." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Google" }] },
                    { "kind": "text", "text": ", when your browser loads the site font (section " },
                    { "kind": "ref", "anchor": "s-4-3", "text": "4.3" },
                    { "kind": "text", "text": ")." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Professional advisers" }]
                    },
                    { "kind": "text", "text": ", such as lawyers and accountants, under a duty of confidentiality." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Authorities" }] },
                    { "kind": "text", "text": ", when the law requires it or to protect people's safety or our legal rights." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "A buyer or successor" }]
                    },
                    { "kind": "text", "text": ", if our business or its assets are sold or reorganised. We would tell you before your data became subject to a different privacy policy." }
                  ],
                  "children": []
                }
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "The customer portal is intended to show administrators the licence, device and weekly allowance information for their organisation." }
              ],
              "clause": "6.2",
              "anchor": "s-6-2"
            }
          ],
          "children": []
        },
        {
          "id": "s-7",
          "number": "7",
          "title": "Where your data is processed",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "We are based in Nigeria. Public desktop installer requests go to DigitalOcean Spaces in SFO3 (San Francisco). The providers and locations for the site, account API, database, notes worker and logs are " },
                { "kind": "placeholder", "name": "SERVICE_HOSTING_LOCATIONS" },
                { "kind": "text", "text": ". Deepgram, OpenAI and other service providers may process data outside the country where the church is located." }
              ],
              "clause": "7.1",
              "anchor": "s-7-1"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "Data protection rules can differ between countries. " },
                { "kind": "placeholder", "name": "TRANSFER_SAFEGUARDS_SUMMARY" }
              ],
              "clause": "7.2",
              "anchor": "s-7-2"
            }
          ],
          "children": []
        },
        {
          "id": "s-8",
          "number": "8",
          "title": "How long we keep personal data",
          "level": 2,
          "blocks": [
            {
              "kind": "table",
              "header": [[{ "kind": "text", "text": "Data" }], [{ "kind": "text", "text": "How long" }]],
              "rows": [
                [
                  [{ "kind": "text", "text": "Account details, including unverified sign-ups" }],
                  [{ "kind": "placeholder", "name": "ACCOUNT_RETENTION" }]
                ],
                [
                  [{ "kind": "text", "text": "Sign-in sessions" }],
                  [
                    { "kind": "text", "text": "Usable until revoked or expired, up to 30 days. Stored-record retention: " },
                    { "kind": "placeholder", "name": "SESSION_RECORD_RETENTION" }
                  ]
                ],
                [
                  [{ "kind": "text", "text": "Email-verification and password-reset links" }],
                  [
                    { "kind": "text", "text": "Usable until used or expired, after 24 hours or 1 hour respectively. Stored-record retention: " },
                    { "kind": "placeholder", "name": "CREDENTIAL_RECORD_RETENTION" }
                  ]
                ],
                [
                  [{ "kind": "text", "text": "Rate-limiting counters and operational logs" }],
                  [{ "kind": "placeholder", "name": "OPERATIONAL_LOG_RETENTION" }]
                ],
                [
                  [
                    { "kind": "text", "text": "Security, licence, device and content-free usage records" }
                  ],
                  [{ "kind": "placeholder", "name": "SECURITY_AND_USAGE_RETENTION" }]
                ],
                [
                  [{ "kind": "text", "text": "Support messages" }],
                  [{ "kind": "placeholder", "name": "SUPPORT_RETENTION" }]
                ],
                [
                  [{ "kind": "text", "text": "SelahCue's temporary notes source and draft" }],
                  [
                    { "kind": "text", "text": "See the intended staging limits in section " },
                    { "kind": "ref", "anchor": "s-3-8", "text": "3.8" }
                  ]
                ],
                [
                  [
                    { "kind": "text", "text": "Audio and transcript text processed by cloud providers" }
                  ],
                  [
                    { "kind": "text", "text": "See provider retention in section " },
                    { "kind": "ref", "anchor": "s-3-8", "text": "3.8" }
                  ]
                ]
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "When we no longer need personal data, we delete it or make it anonymous. We may keep some data for longer if the law requires it or if we need it to establish, exercise or defend legal claims." }
              ]
            }
          ],
          "children": []
        },
        {
          "id": "s-9",
          "number": "9",
          "title": "How we protect personal data",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "We use technical and organisational measures suited to the risk. They include:" }
              ],
              "clause": "9.1",
              "anchor": "s-9-1"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [{ "kind": "text", "text": "storing passwords only as salted one-way hashes;" }],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "storing session, email-link, enrolment-key and device credentials only in hashed form;" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "signing everyone out of all sessions when a password changes;" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "temporarily locking sign-in after repeated failed attempts;" }
                  ],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "limiting the rate of sensitive requests;" }],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "serving our website and online services over encrypted connections (HTTPS); and" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "in the desktop app, encrypting the transcript database on disk and keeping credentials in the operating system's secure store." }
                  ],
                  "children": []
                }
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "No system is perfectly secure. If a breach affects your personal data and puts you at risk, we tell you without undue delay, and we inform the authorities where the law requires us to." }
              ],
              "clause": "9.2",
              "anchor": "s-9-2"
            }
          ],
          "children": []
        },
        {
          "id": "s-10",
          "number": "10",
          "title": "Children",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "SelahCue is a tool for church production teams. It is not directed at children. You must be at least 18 years old to create an account." }
              ],
              "clause": "10.1",
              "anchor": "s-10-1"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "We do not knowingly collect personal data from children. If you believe a child has given us personal data, contact us and we will delete it." }
              ],
              "clause": "10.2",
              "anchor": "s-10-2"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "Churches using live transcription, and especially cloud transcription, should take particular care where children may be heard, for example in family services or children's ministry (see section " },
                { "kind": "ref", "anchor": "s-2-3", "text": "2.3" },
                { "kind": "text", "text": ")." }
              ],
              "clause": "10.3",
              "anchor": "s-10-3"
            }
          ],
          "children": []
        },
        {
          "id": "s-11",
          "number": "11",
          "title": "Your choices and rights",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "Depending on where you live, you may have rights such as to:" }
              ],
              "clause": "11.1",
              "anchor": "s-11-1"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    { "kind": "text", "text": "find out what personal data we hold about you, and get a copy;" }
                  ],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "have inaccurate data corrected;" }],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "have your data deleted;" }],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "object to, or ask us to limit, how we use your data;" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "receive your data in a format you can take elsewhere; and" }
                  ],
                  "children": []
                },
                {
                  "inline": [{ "kind": "text", "text": "withdraw consent, where we rely on it." }],
                  "children": []
                }
              ]
            },
            {
              "kind": "paragraph",
              "inline": [
                {
                  "kind": "strong",
                  "children": [{ "kind": "text", "text": "Requests to close or delete an account." }]
                },
                { "kind": "text", "text": " Email " },
                { "kind": "code", "text": "support@selahcueapp.com" },
                { "kind": "text", "text": " to request closure or deletion. We may ask you to confirm your identity or your authority to act for your organisation." }
              ],
              "clause": "11.2",
              "anchor": "s-11-2"
            },
            {
              "kind": "paragraph",
              "inline": [
                {
                  "kind": "strong",
                  "children": [{ "kind": "text", "text": "Access and data copies." }]
                },
                { "kind": "text", "text": " Email " },
                { "kind": "code", "text": "support@selahcueapp.com" },
                { "kind": "text", "text": " to request a copy of your personal data. We may ask you to confirm your identity before providing it." }
              ],
              "clause": "11.3",
              "anchor": "s-11-3"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "strong", "children": [{ "kind": "text", "text": "Other requests." }] },
                { "kind": "text", "text": " For other requests about your personal data, email " },
                { "kind": "code", "text": "support@selahcueapp.com" },
                { "kind": "text", "text": ". " },
                { "kind": "placeholder", "name": "RIGHTS_REQUEST_PROCESS_AND_TIMING" }
              ],
              "clause": "11.4",
              "anchor": "s-11-4"
            },
            {
              "kind": "paragraph",
              "inline": [
                {
                  "kind": "strong",
                  "children": [{ "kind": "text", "text": "Data your church holds." }]
                },
                { "kind": "text", "text": " We cannot access transcripts or other content stored on your church's computers. To ask about that data, contact the church. For data sent to our cloud features, we help your church respond to your request." }
              ],
              "clause": "11.5",
              "anchor": "s-11-5"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "strong", "children": [{ "kind": "text", "text": "Concerns." }] },
                { "kind": "text", "text": " Please contact us first so we can try to help. You can also contact the data protection authority where you live." }
              ],
              "clause": "11.6",
              "anchor": "s-11-6"
            }
          ],
          "children": []
        },
        {
          "id": "s-12",
          "number": "12",
          "title": "Changes to this policy",
          "level": 2,
          "blocks": [
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "We update this policy when our services or the law change. We post the new version at " },
                { "kind": "code", "text": "https://selahcueapp.com/privacy" },
                { "kind": "text", "text": " and change the effective date." }
              ],
              "clause": "12.1",
              "anchor": "s-12-1"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "If a change materially affects how we use your personal data, we tell account holders by email or in the product before it takes effect. Where the law requires your consent to a change, we ask for it." }
              ],
              "clause": "12.2",
              "anchor": "s-12-2"
            }
          ],
          "children": []
        },
        {
          "id": "s-13",
          "number": "13",
          "title": "Contact us",
          "level": 2,
          "blocks": [
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Email:" }] },
                    { "kind": "text", "text": " " },
                    { "kind": "code", "text": "support@selahcueapp.com" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Post:" }] },
                    { "kind": "text", "text": " First Pavilion Technologies, 4, Law Castle, Taiwo Street, Omida, Abeokuta, Ogun State, Nigeria" }
                  ],
                  "children": []
                }
              ]
            }
          ],
          "children": []
        }
      ]
    }
  ]
}
