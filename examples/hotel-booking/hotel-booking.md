# pytest-given — pytest-given

## ✓ Carol picks a suite for the group
`examples/hotel-booking/test_hotel_booking.py:148::test_pick_suite`

- **given** our organizer «Carol»
- **given** the «Deluxe Suite» is listed as available
- **when** «Carol» «searches for» a «Room»
- **when** «Carol» «selects» the «Deluxe Suite»
- **then** the «Deluxe Suite» is held for «Carol»

## ✓ Carol completes the booking for both guests
`examples/hotel-booking/test_hotel_booking.py:163::test_complete_booking`

- **given** our organizer «Carol»
- **given** our guest «Alice»
- **given** our guest «Bob»
- **given** «Carol» has «selected» the «Deluxe Suite»
- **when** «Carol» «adds» «Alice» and «Bob» to the «Booking»
- **when** «Carol» «submits» the «Payment» for the «Booking»
- **then** the «Booking System» «confirms» the «Booking»
- **then** the «Booking System» «sends» the «Confirmation» to «Alice» and «Bob»

## ✓ Alice cancels her booking and is refunded
`examples/hotel-booking/test_hotel_booking.py:240::test_cancel_booking`

- **given** our guest «Alice»
- **given** «Alice» has a confirmed «Booking» she paid for
- **when** «Alice» «cancels» the «Booking»
- **then** the «Booking System» «refunds» the «Payment» for the «Booking»
- **then** the «Booking System» «sends» a «Confirmation» to «Alice»

## ✗ Payment is declined — the booking is not finalized · 4 cases
`examples/hotel-booking/test_hotel_booking.py:198::test_payment_declined`

- **given** our organizer «Carol»
- **given** our guest «Alice»
- **given** our guest «Bob»
- **given** «Carol» has «added» «Alice» and «Bob» to the «Booking»
- **when** «Carol» «submits» the «Payment» by {payment_method} for the «Booking»
- **then** the «Booking System» «rejects» the «Payment» because of {decline_reason}
- **then** the «Booking» stays pending and no «Confirmation» is sent to «Alice» or «Bob»

| payment_method | decline_reason | |
|---|---|---|
| credit card | insufficient funds | ✓ |
| debit card | expired card | ✓ |
| bank transfer | fraud check failed | ✓ |
| gift card | partial balance | ✗ |
