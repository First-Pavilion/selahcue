const endsOn = '5 May 2027'
const cloudTranscriptionHours = 3
const sermonNotes = 5
const devices = 10

/** Public display copy. The account service owns entitlement and usage. */
export const betaOffer = Object.freeze({
  endsOn,
  cloudTranscriptionHours,
  sermonNotes,
  devices,
  summary: `The SelahCue public beta is free and includes every feature until ${endsOn}: up to ${devices} devices, no watermark, and ${cloudTranscriptionHours} hours of cloud transcription and ${sermonNotes} sermon notes per church each week.`,
  afterBeta:
    'After the beta, your church keeps using SelahCue on the Free plan, which runs on one computer: the first one you set up. Paid plans will be announced before the beta ends.',
  signupTo: '/signup',
  downloadTo: '/download#public-downloads',
})
