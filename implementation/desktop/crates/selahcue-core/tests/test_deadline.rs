#![allow(clippy::unwrap_used)]
use selahcue_core::deadline::{AccessDeadline, Clock, ClockReading, DeadlineError};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
struct FakeClock(Mutex<ClockReading>);
impl Clock for FakeClock {
    fn now(&self) -> ClockReading {
        *self.0.lock().unwrap()
    }
}
#[test]
fn exact_boundary_and_clock_rollback_cannot_renew_admitted_budget() {
    let wall = UNIX_EPOCH + Duration::from_secs(100);
    let mono = Instant::now();
    let clock = Arc::new(FakeClock(Mutex::new(ClockReading {
        wall: Some(wall),
        monotonic: mono,
    })));
    let d = AccessDeadline::admit(wall + Duration::from_secs(10), clock.clone()).unwrap();
    assert_eq!(d.remaining().unwrap(), Duration::from_secs(10));
    *clock.0.lock().unwrap() = ClockReading {
        wall: Some(wall - Duration::from_secs(20)),
        monotonic: mono + Duration::from_secs(9),
    };
    assert_eq!(d.remaining().unwrap(), Duration::from_secs(1));
    *clock.0.lock().unwrap() = ClockReading {
        wall: Some(wall),
        monotonic: mono + Duration::from_secs(10),
    };
    assert_eq!(d.remaining(), Err(DeadlineError::Expired));
}
#[test]
fn forward_wall_jump_and_unavailable_clock_fail_closed() {
    let wall = SystemTime::now();
    let mono = Instant::now();
    let clock = Arc::new(FakeClock(Mutex::new(ClockReading {
        wall: Some(wall),
        monotonic: mono,
    })));
    let d = AccessDeadline::admit(wall + Duration::from_secs(10), clock.clone()).unwrap();
    *clock.0.lock().unwrap() = ClockReading {
        wall: Some(wall + Duration::from_secs(10)),
        monotonic: mono,
    };
    assert_eq!(d.remaining(), Err(DeadlineError::Expired));
    *clock.0.lock().unwrap() = ClockReading {
        wall: Some(wall),
        monotonic: mono,
    };
    assert_eq!(
        d.clone().remaining(),
        Err(DeadlineError::Expired),
        "a cloned worker/source admission shares retirement after forward-clock expiry"
    );
    let fresh = AccessDeadline::admit(wall + Duration::from_secs(10), clock.clone()).unwrap();
    *clock.0.lock().unwrap() = ClockReading {
        wall: None,
        monotonic: mono,
    };
    assert_eq!(fresh.remaining(), Err(DeadlineError::Unavailable));
    *clock.0.lock().unwrap() = ClockReading {
        wall: Some(wall),
        monotonic: mono,
    };
    assert_eq!(
        fresh.remaining(),
        Err(DeadlineError::Unavailable),
        "invalid clock retires the admission"
    );
}
#[test]
fn expiry_itself_is_absolute_across_new_admission_or_restart() {
    let expiry = UNIX_EPOCH + Duration::from_secs(1_809_129_599);
    let mono = Instant::now();
    for now in [expiry, expiry + Duration::from_secs(1)] {
        let clock = Arc::new(FakeClock(Mutex::new(ClockReading {
            wall: Some(now),
            monotonic: mono,
        })));
        assert!(matches!(
            AccessDeadline::admit(expiry, clock),
            Err(DeadlineError::Expired)
        ));
    }
}
