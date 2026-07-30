import { describe, expect, it } from 'vitest'

import { decodeVapidPublicKey } from '../push'


describe('Web Push helpers', () => {
  it('decodes URL-safe base64 VAPID public keys', () => {
    expect(Array.from(decodeVapidPublicKey('AQID-_8'))).toEqual([1, 2, 3, 251, 255])
  })
})
