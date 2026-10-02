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
          { "kind": "text", "text": "Version 0.3 (draft, 2026-10-01). Status: Draft — every " },
          { "kind": "placeholder", "name": "PLACEHOLDER" },
          { "kind": "text", "text": " must be filled and every launch-readiness condition in " },
          { "kind": "code", "text": "docs/legal/LEGAL-DRAFT-NOTES.md" },
          { "kind": "text", "text": " §4 must be satisfied before publication. This policy describes SelahCue as it operates at launch. Publishing it while any launch-readiness condition is unmet would make it inaccurate. The SelahCue Controller mobile app also has its own policy (" },
          { "kind": "code", "text": "docs/legal/PRIVACY.md" },
          { "kind": "text", "text": "), which this policy does not replace." }
        ]
      }
    ]
  },
  "version": { "number": "0.3", "status": "draft", "date": "2026-10-01", "line": "Version 0.3 (draft, 2026-10-01)", "source": "banner" },
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
        { "kind": "text", "text": " " },
        { "kind": "placeholder", "name": "REGISTERED_ADDRESS" }
      ],
      "children": []
    },
    {
      "inline": [
        { "kind": "strong", "children": [{ "kind": "text", "text": "Registration number:" }] },
        { "kind": "text", "text": " " },
        { "kind": "placeholder", "name": "COMPANY_REGISTRATION_NUMBER" }
      ],
      "children": []
    },
    {
      "inline": [
        { "kind": "strong", "children": [{ "kind": "text", "text": "Privacy contact:" }] },
        { "kind": "text", "text": " " },
        { "kind": "placeholder", "name": "PRIVACY_CONTACT_EMAIL" }
      ],
      "children": []
    },
    {
      "inline": [
        { "kind": "strong", "children": [{ "kind": "text", "text": "Effective date:" }] },
        { "kind": "text", "text": " " },
        { "kind": "placeholder", "name": "EFFECTIVE_DATE" }
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
                  { "kind": "text", "text": "Your church's content stays on your church's computers." }
                ]
              },
              { "kind": "text", "text": " Slides, songs, scripture, media, service plans, sermon transcripts and sermon notes are stored on the computers where you run SelahCue. We do not receive them unless you use a cloud feature or send them to us." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Live transcription runs on your computer by default." }]
              },
              { "kind": "text", "text": " Audio is not sent anywhere. The first time you use it, the app downloads a speech-recognition model file from Hugging Face, a third-party website." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Cloud features are optional and off by default." }]
              },
              { "kind": "text", "text": " Only an administrator can turn them on. Cloud transcription sends live audio to Deepgram. AI sermon notes send the finished transcript text to OpenAI. That data leaves your church's network and can be processed in another country." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "The mobile controller talks only to your desktop" }]
              },
              { "kind": "text", "text": ", over your own local network." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Your SelahCue account" }]
              },
              { "kind": "text", "text": " holds your email address, a password (stored only in scrambled, one-way form), your church or organisation name, your country and time zone, and, if you give it, your name." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Licences, devices and downloads." }]
              },
              { "kind": "text", "text": " When you activate SelahCue on a computer, we record a device identifier, its platform, app version and the name you give it. We also record what you download." }
            ],
            "children": []
          },
          {
            "inline": [
              { "kind": "strong", "children": [{ "kind": "text", "text": "Payments" }] },
              { "kind": "text", "text": " go through Paystack's checkout. Paystack collects your card or bank details. Your full card number never reaches us." }
            ],
            "children": []
          },
          {
            "inline": [
              {
                "kind": "strong",
                "children": [{ "kind": "text", "text": "Our website uses only the cookies it needs" }]
              },
              { "kind": "text", "text": " to keep you signed in and to protect our forms, plus Paystack's own cookies on its checkout. We do not use advertising or analytics cookies. Our website loads a font from Google, so Google receives your IP address when you visit." }
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
              { "kind": "strong", "children": [{ "kind": "text", "text": "You have choices." }] },
              { "kind": "text", "text": " You can delete your account yourself in your account settings. To get a copy of your data, or for any other request, email " },
              { "kind": "placeholder", "name": "PRIVACY_CONTACT_EMAIL" },
              { "kind": "text", "text": "." }
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
                    { "kind": "placeholder", "name": "WEBSITE_URL" },
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
                  "inline": [{ "kind": "text", "text": "buy or manage a SelahCue plan;" }],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "activate SelahCue on a computer, or download SelahCue, updates or Bible translations;" }
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
                { "kind": "text", "text": " is used. The exception is audio and transcripts sent to our optional cloud features: we handle those only to provide the feature to your church (see section " },
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
                    { "kind": "text", "text": "the SelahCue Controller mobile app, which has its own privacy policy at " },
                    { "kind": "placeholder", "name": "CONTROLLER_PRIVACY_POLICY_URL" },
                    { "kind": "text", "text": "; or" }
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
                { "kind": "text", "text": "We do not have access to this data. Your church decides what is created, how long it is kept and who can use the computer, and is responsible for it." }
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
                { "kind": "text", "text": " These features send data across your church's local network, but not to us:" }
              ],
              "clause": "2.5",
              "anchor": "s-2-5"
            },
            {
              "kind": "list",
              "items": [
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Mobile controller." }]
                    },
                    { "kind": "text", "text": " A paired phone or tablet receives the current and next slide, timers and, where enabled, a live transcript preview. The connection is encrypted and tied to the specific desktop the device was paired with." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Discovery." }] },
                    { "kind": "text", "text": " The desktop app announces itself on the local network so paired devices can find it." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "NDI output." }] },
                    { "kind": "text", "text": " If you turn on NDI output, the app broadcasts your presentation video on the local network for other NDI equipment to receive." }
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
                    { "kind": "text", "text": "You do not need an account to use SelahCue's core presentation features. You need one to buy and manage a plan, activate SelahCue on your computers, manage your devices, and use cloud features." }
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
                      [
                        { "kind": "text", "text": "To set up your account and apply the right terms and taxes" }
                      ],
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
                      [{ "kind": "text", "text": "Billing contact email (optional)" }],
                      [{ "kind": "text", "text": "You" }],
                      [{ "kind": "text", "text": "To send invoices and billing notices" }],
                      [{ "kind": "text", "text": "To provide the service" }]
                    ],
                    [
                      [
                        { "kind": "text", "text": "Account role (administrator or member) and status" }
                      ],
                      [{ "kind": "text", "text": "Created by our system" }],
                      [
                        { "kind": "text", "text": "To control who can manage plans, licences and devices" }
                      ],
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
                        { "kind": "text", "text": "Record of your acceptance of our Terms and this policy (version and time)" }
                      ],
                      [{ "kind": "text", "text": "Created by our system when you accept" }],
                      [
                        { "kind": "text", "text": "To show which terms apply to you and when you agreed" }
                      ],
                      [
                        { "kind": "text", "text": "To provide the service; to meet legal requirements" }
                      ]
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
                        { "kind": "text", "text": "Notes our staff record about your account, and your plan and licence details" }
                      ],
                      [{ "kind": "text", "text": "Our staff and our system" }],
                      [
                        { "kind": "text", "text": "To support you and manage your plan and licence" }
                      ],
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
                    { "kind": "text", "text": "We send you these emails because they are needed to run your account and your plan:" }
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
                        { "kind": "text", "text": "a notice if someone tries to create an account with your email address. We send this instead of telling the person signing up that the address is already registered;" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        { "kind": "text", "text": "notices about your licence and plan, such as renewal reminders, and notices that a licence has expired or been suspended; and" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [{ "kind": "text", "text": "receipts, invoices and payment notices." }],
                      "children": []
                    }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "We send these emails through " },
                    { "kind": "placeholder", "name": "EMAIL_DELIVERY_PROVIDER" },
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
                        { "kind": "text", "text": "a device identifier generated by the app (" },
                        { "kind": "placeholder", "name": "DEVICE_FINGERPRINT_METHOD" },
                        { "kind": "text", "text": ");" }
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
                    { "kind": "text", "text": " We keep SelahCue installers in private, encrypted storage provided by " },
                    { "kind": "placeholder", "name": "DOWNLOAD_HOSTING_PROVIDER" },
                    { "kind": "text", "text": " in " },
                    { "kind": "placeholder", "name": "DOWNLOAD_HOSTING_REGION" },
                    { "kind": "text", "text": ". When you download SelahCue, an update or an additional Bible translation through your account or an activated device, we give you a download link that expires after a short time. We record what was downloaded, for which platform, when, and for which account or device. The file comes directly from " },
                    { "kind": "placeholder", "name": "DOWNLOAD_HOSTING_PROVIDER" },
                    { "kind": "text", "text": ", which receives your IP address and standard request information when you download." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "We use this information to apply your plan's device limit and usage allowances, to show your administrators which devices are active, to let them remove devices, to deliver the software and content your plan includes, and to prevent misuse of licences." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "Activation, check-ins and downloads do not send us your slides, transcripts, audio or network logs." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "If your organisation uses an enrolment key to activate, we store the key only in hashed form, plus a short masked version so you and our staff can recognise it." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-4",
              "number": "3.4",
              "title": "Plans and payments",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "When you buy a paid plan, you pay on a checkout page provided by Paystack, our payment processor. Paystack collects your card or bank details directly. Your full card number never reaches our servers, and we do not store it. Paystack sends us " },
                    { "kind": "placeholder", "name": "PAYMENT_DATA_RECEIVED" },
                    { "kind": "text", "text": ", and Paystack handles your payment details under its own terms and privacy policy." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "We keep your plan, billing history, invoices and billing contact details. We use them to take payment, manage your subscription, send receipts and notices, handle refunds and failed payments, and keep the tax and accounting records the law requires." }
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
                    { "kind": "text", "text": "When you use our website or our online services, our servers and our hosting provider " },
                    { "kind": "placeholder", "name": "HOSTING_PROVIDER" },
                    { "kind": "text", "text": " process technical information, including your IP address, browser type, and the pages and requests you make. We use it to deliver the website, keep it secure, and fix problems." }
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
                        { "kind": "text", "text": " To stop abuse, such as repeated password-reset requests, we count requests from each network address for a short time. For IPv6 addresses we keep only the network part. These counters expire within one hour." }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "Server logs." }]
                        },
                        { "kind": "text", "text": " We keep server logs for " },
                        { "kind": "placeholder", "name": "SERVER_LOG_RETENTION" },
                        { "kind": "text", "text": "." }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "Security and audit records." }]
                        },
                        { "kind": "text", "text": " We record important account, licence, plan and cloud-feature actions, such as sign-up, device activation, licence changes, and cloud-feature requests that were allowed or refused. Each record says who acted (by internal identifier), what changed, the result and when. Passwords, keys and access credentials are never included. We keep these records for " },
                        { "kind": "placeholder", "name": "AUDIT_RECORD_RETENTION" },
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
                    { "kind": "text", "text": "If you use the contact form on our website, or email us at " },
                    { "kind": "placeholder", "name": "SUPPORT_CONTACT_EMAIL" },
                    { "kind": "text", "text": " or " },
                    { "kind": "placeholder", "name": "PRIVACY_CONTACT_EMAIL" },
                    { "kind": "text", "text": ", we use your name, contact details and message, and anything you attach, to reply and to improve our help. Please do not send us transcripts or other church content unless we need it to solve your problem." }
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
                          "children": [{ "kind": "text", "text": "activate, check in and download" }]
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
                        { "kind": "text", "text": "). Your computer's IP address and a standard web request go to Hugging Face, as with any download. The app checks the file has not been altered before using it. Hugging Face handles that request under its own privacy policy; and" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "download Bible translations" }]
                        },
                        { "kind": "text", "text": " that are not built into the app, from " },
                        { "kind": "placeholder", "name": "TRANSLATION_DOWNLOAD_HOST" },
                        { "kind": "text", "text": ". The translations built into the app need no download." }
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
                  "inline": [{ "kind": "text", "text": "SelahCue offers two optional cloud features:" }]
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
                        { "kind": "text", "text": " While it is switched on and listening, the desktop app streams live audio from the selected microphone directly to Deepgram, using a short-lived access credential our servers issue. Deepgram returns text. We do not receive the audio." }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        {
                          "kind": "strong",
                          "children": [{ "kind": "text", "text": "AI sermon notes." }]
                        },
                        { "kind": "text", "text": " When an operator presses Generate, the app sends the completed transcript text (never audio) to OpenAI " },
                        { "kind": "placeholder", "name": "NOTES_ROUTE" },
                        { "kind": "text", "text": ", which returns a draft." }
                      ],
                      "children": []
                    }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "These features are off by default. Only an administrator can turn them on, separately for each feature, after the app shows what data is sent, to which provider, and that it can be processed in another country. While cloud transcription is active, the app shows an indicator." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "When you use these features, your sermon audio or transcript leaves your church's network and is processed on Deepgram's or OpenAI's servers, which can be in a different country from yours. Deepgram and OpenAI handle this data under their own terms and privacy policies, which say how long they keep it and whether they use it to improve their services. We and they handle it only to provide the feature to your church. Data sent to cloud features is kept for " },
                    { "kind": "placeholder", "name": "PROVIDER_RETENTION" },
                    { "kind": "text", "text": "." }
                  ]
                },
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "To apply your plan's usage allowances, we record how much of each feature your organisation uses (for example, transcription time and number of note drafts), and each request that was allowed or refused, with the reason. These usage records do not contain audio or sermon content." }
                  ]
                }
              ],
              "children": []
            },
            {
              "id": "s-3-9",
              "number": "3.9",
              "title": "Licensed Bible translations",
              "level": 3,
              "blocks": [
                {
                  "kind": "paragraph",
                  "inline": [
                    { "kind": "text", "text": "Some plans include copyrighted Bible translations licensed from their publishers. When your plan includes one, the app downloads it after your device is activated. Our licences with publishers require us to report " },
                    { "kind": "placeholder", "name": "PUBLISHER_REPORTING_DATA" },
                    { "kind": "text", "text": " to them. We do not send publishers your sermon content or transcripts." }
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
                ],
                [
                  [{ "kind": "text", "text": "Paystack checkout cookies and scripts" }],
                  [{ "kind": "text", "text": "Set by Paystack on its checkout page" }],
                  [{ "kind": "text", "text": "Process your payment securely and prevent fraud" }],
                  [
                    { "kind": "text", "text": "As set by Paystack; Paystack's cookie policy applies" }
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
                { "kind": "text", "text": "If you do not give us the information marked as needed at sign-up or checkout, we cannot create your account or process your purchase." }
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
              "inline": [{ "kind": "text", "text": "We share personal data only with:" }],
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
                      "children": [{ "kind": "text", "text": "Service providers" }]
                    },
                    { "kind": "text", "text": " that run parts of our service for us:" }
                  ],
                  "children": [
                    {
                      "inline": [
                        { "kind": "text", "text": "hosting: " },
                        { "kind": "placeholder", "name": "HOSTING_PROVIDER" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        { "kind": "text", "text": "installer storage and downloads: " },
                        { "kind": "placeholder", "name": "DOWNLOAD_HOSTING_PROVIDER" }
                      ],
                      "children": []
                    },
                    {
                      "inline": [
                        { "kind": "text", "text": "email delivery: " },
                        { "kind": "placeholder", "name": "EMAIL_DELIVERY_PROVIDER" }
                      ],
                      "children": []
                    }
                  ]
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Paystack" }] },
                    { "kind": "text", "text": ", which processes payments for us (section " },
                    { "kind": "ref", "anchor": "s-3-4", "text": "3.4" },
                    { "kind": "text", "text": ")." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Deepgram and OpenAI" }]
                    },
                    { "kind": "text", "text": ", when an administrator has turned on a cloud feature (section " },
                    { "kind": "ref", "anchor": "s-3-8", "text": "3.8" },
                    { "kind": "text", "text": ")." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    {
                      "kind": "strong",
                      "children": [{ "kind": "text", "text": "Bible publishers" }]
                    },
                    { "kind": "text", "text": ", to the extent described in section " },
                    { "kind": "ref", "anchor": "s-3-9", "text": "3.9" },
                    { "kind": "text", "text": "." }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Google" }] },
                    { "kind": "text", "text": ", when our website loads the Inter font (section " },
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
                { "kind": "text", "text": "Your organisation's administrators can see, in the customer portal, the account information of members of the same organisation, and the organisation's plan, licence, devices, usage and billing history." }
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
                { "kind": "text", "text": "We are based in " },
                { "kind": "placeholder", "name": "COUNTRY_OF_ESTABLISHMENT" },
                { "kind": "text", "text": ". Our servers run with " },
                { "kind": "placeholder", "name": "HOSTING_PROVIDER" },
                { "kind": "text", "text": " in " },
                { "kind": "placeholder", "name": "HOSTING_REGION" },
                { "kind": "text", "text": ", and our installers are stored with " },
                { "kind": "placeholder", "name": "DOWNLOAD_HOSTING_PROVIDER" },
                { "kind": "text", "text": " in " },
                { "kind": "placeholder", "name": "DOWNLOAD_HOSTING_REGION" },
                { "kind": "text", "text": ". Paystack, Deepgram, OpenAI and our other providers process data on their own servers." }
              ],
              "clause": "7.1",
              "anchor": "s-7-1"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "text", "text": "These places can be outside your country, and the data protection rules there may differ from the rules where you live. " },
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
                  [{ "kind": "text", "text": "Account details" }],
                  [
                    { "kind": "text", "text": "While your account is open, then " },
                    { "kind": "placeholder", "name": "ACCOUNT_RETENTION_AFTER_CLOSURE" }
                  ]
                ],
                [
                  [{ "kind": "text", "text": "Accounts that are never verified" }],
                  [{ "kind": "placeholder", "name": "UNVERIFIED_SIGNUP_RETENTION" }]
                ],
                [
                  [{ "kind": "text", "text": "Sign-in sessions" }],
                  [
                    { "kind": "text", "text": "Until you sign out or they expire (up to 30 days); expired records are deleted by a nightly job" }
                  ]
                ],
                [
                  [{ "kind": "text", "text": "Email-verification and password-reset links" }],
                  [
                    { "kind": "text", "text": "Until used or expired (24 hours and 1 hour); expired records are deleted by a nightly job" }
                  ]
                ],
                [
                  [{ "kind": "text", "text": "Rate-limiting counters" }],
                  [{ "kind": "text", "text": "Up to 1 hour" }]
                ],
                [
                  [{ "kind": "text", "text": "Server logs" }],
                  [{ "kind": "placeholder", "name": "SERVER_LOG_RETENTION" }]
                ],
                [
                  [{ "kind": "text", "text": "Security and audit records" }],
                  [{ "kind": "placeholder", "name": "AUDIT_RECORD_RETENTION" }]
                ],
                [
                  [{ "kind": "text", "text": "Licence, device, download and usage records" }],
                  [
                    { "kind": "text", "text": "While your organisation's account is open, then " },
                    { "kind": "placeholder", "name": "LICENCE_RECORD_RETENTION" }
                  ]
                ],
                [
                  [{ "kind": "text", "text": "Payment, invoice and tax records" }],
                  [{ "kind": "placeholder", "name": "FINANCIAL_RECORD_RETENTION" }]
                ],
                [
                  [{ "kind": "text", "text": "Support messages" }],
                  [{ "kind": "placeholder", "name": "SUPPORT_RETENTION" }]
                ],
                [
                  [{ "kind": "text", "text": "Audio and transcripts sent to cloud features" }],
                  [{ "kind": "placeholder", "name": "PROVIDER_RETENTION" }]
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
                    { "kind": "text", "text": "serving our website and services only over encrypted connections (HTTPS);" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "keeping installers in private, encrypted storage and delivering them only through expiring links; and" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "text", "text": "in the desktop app, encrypting the transcript database on disk, keeping credentials in the operating system's secure store, and encrypting the local-network link to paired mobile devices." }
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
                { "kind": "text", "text": "SelahCue is a tool for church production teams. It is not directed at children. You must be at least " },
                { "kind": "placeholder", "name": "MINIMUM_ACCOUNT_AGE" },
                { "kind": "text", "text": " to create an account, and we ask you to confirm this at sign-up." }
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
                  "children": [{ "kind": "text", "text": "Deleting your account." }]
                },
                { "kind": "text", "text": " You can delete your user account yourself in your account settings. An administrator can close your organisation's account in the customer portal. When we delete an account, we delete or anonymise the personal data in it, and we keep security and audit records only in a form that no longer identifies you, except where the law requires us to keep them." }
              ],
              "clause": "11.2",
              "anchor": "s-11-2"
            },
            {
              "kind": "paragraph",
              "inline": [
                {
                  "kind": "strong",
                  "children": [{ "kind": "text", "text": "Getting a copy of your data." }]
                },
                { "kind": "text", "text": " Email " },
                { "kind": "placeholder", "name": "PRIVACY_CONTACT_EMAIL" },
                { "kind": "text", "text": ". We confirm your identity, then prepare an export of your account data and send it to you through a download link that expires. We do this within " },
                { "kind": "placeholder", "name": "DSAR_RESPONSE_TIME" },
                { "kind": "text", "text": "." }
              ],
              "clause": "11.3",
              "anchor": "s-11-3"
            },
            {
              "kind": "paragraph",
              "inline": [
                { "kind": "strong", "children": [{ "kind": "text", "text": "Other requests." }] },
                { "kind": "text", "text": " For any other request about your personal data, email " },
                { "kind": "placeholder", "name": "PRIVACY_CONTACT_EMAIL" },
                { "kind": "text", "text": ". We may ask you to confirm your identity, and we reply within " },
                { "kind": "placeholder", "name": "DSAR_RESPONSE_TIME" },
                { "kind": "text", "text": ". We do not charge for requests unless a request is clearly unfounded or excessive." }
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
                { "kind": "placeholder", "name": "PRIVACY_POLICY_URL" },
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
                    { "kind": "placeholder", "name": "PRIVACY_CONTACT_EMAIL" }
                  ],
                  "children": []
                },
                {
                  "inline": [
                    { "kind": "strong", "children": [{ "kind": "text", "text": "Post:" }] },
                    { "kind": "text", "text": " First Pavilion Technologies, " },
                    { "kind": "placeholder", "name": "REGISTERED_ADDRESS" }
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
