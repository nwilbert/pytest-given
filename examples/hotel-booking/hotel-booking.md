# pytest-given — Hotel Booking Example

## ✓ Carol picks a suite for the group
`examples/hotel-booking/test_hotel_booking.py:166::test_pick_suite`

- **given** our organizer «Carol»
- **given** the «Deluxe Suite» is listed as available
- **when** «Carol» searches for a «Room»
- **when** «Carol» selects the «Deluxe Suite»
- **then** the «Deluxe Suite» is held for the group

## ✓ Carol completes the booking for both guests
`examples/hotel-booking/test_hotel_booking.py:186::test_complete_booking`

- **given** our organizer «Carol»
- **given** our guest «Alice»
- **given** our guest «Bob»
- **given** «Carol» has selected the «Deluxe Suite»
- **when** «Carol» adds «Alice» and «Bob» to the «Booking»
- **when** «Carol» submits the «Payment» for the «Booking»
- **then** the «Booking System» «confirms» the «Booking»
- **then** the «Booking System» sends the «Confirmation» to «Alice» and «Bob»
- **when** «Alice» and «Bob» check in to the «Deluxe Suite»
- **then** both guests are checked in

## ✗ Payment is declined — the booking is not finalized · 4 cases
`examples/hotel-booking/test_hotel_booking.py:230::test_payment_declined`

- **given** our organizer «Carol»
- **given** our guest «Alice»
- **given** our guest «Bob»
- **given** «Carol» has added «Alice» and «Bob» to the «Booking»
- **when** «Carol» submits the «Payment» by {payment_method} for the «Booking»
- **then** the «Booking System» «declines» the «Payment» because of {decline_reason}
- **then** the «Booking» stays pending and no «Confirmation» is sent to «Alice» or «Bob»

| payment_method | decline_reason | |
|---|---|---|
| credit card | insufficient funds | ✓ |
| debit card | expired card | ✓ |
| bank transfer | fraud check failed | ✓ |
| gift card | partial balance | ✗ |

- **gift card, partial balance** — failed:
  > assert 'unsupported payment method' == 'partial balance'
  > test_hotel_booking.py:268 in test_payment_declined

## ✓ Alice cancels her booking and is refunded
`examples/hotel-booking/test_hotel_booking.py:277::test_cancel_booking`

- **given** our guest «Alice»
- **given** «Alice» has a confirmed «Booking» she paid for
- **when** «Alice» «cancels» the «Booking»
- **then** the «Booking System» «refunds» the «Payment» for the «Booking»
- **then** the «Booking System» sends a «Confirmation» to «Alice»

## ✓ Alice checks in, then cancels a later booking
`examples/hotel-booking/test_hotel_booking.py:311::test_check_in_then_cancel`

- **given** our guest «Alice»
- **given** «Alice» has a confirmed «Booking» now and one next month
- **when** «Alice» checks in to the «Deluxe Suite»
- **when** «Alice» «cancels» her later «Booking»
- **then** the later booking is cancelled
- **then** her current stay is still checked in
