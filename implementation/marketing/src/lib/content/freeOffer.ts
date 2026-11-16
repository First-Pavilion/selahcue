const cloudTranscriptionMinutes = 20
const sermonNotes = 1

/** Public display copy. The account service owns entitlement and usage. */
export const freeOffer = Object.freeze({
  cloudTranscriptionMinutes,
  sermonNotes,
  summary: `The ongoing Free plan includes ${cloudTranscriptionMinutes} cloud transcription minutes and ${sermonNotes} sermon note per church per week.`,
  paidLater: 'Paid subscriptions will come later.',
  signupTo: '/signup',
  downloadTo: '/download#public-downloads',
})
