use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum AccountWebDestination {
    Signup,
    ForgotPassword,
    Verification,
    Account,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum AccountUiError {
    BrowserOpenFailed,
}

impl AccountWebDestination {
    pub(super) fn open_with<E>(
        self,
        launch: impl FnOnce(&'static str) -> Result<(), E>,
    ) -> Result<(), AccountUiError> {
        let url = match self {
            Self::Signup => "https://selahcueapp.com/signup",
            Self::ForgotPassword => "https://selahcueapp.com/forgot-password",
            Self::Verification => "https://selahcueapp.com/verify",
            Self::Account => "https://selahcueapp.com/account",
        };
        launch(url).map_err(|_| AccountUiError::BrowserOpenFailed)
    }
}
