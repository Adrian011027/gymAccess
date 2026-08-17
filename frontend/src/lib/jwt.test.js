import { describe, expect, it } from 'vitest'
import { leerToken } from './jwt'
import { tokenFalso } from '../test/utils'

describe('leerToken', () => {
  it('devuelve el payload de un token válido', () => {
    const payload = { nombre: 'Diego', rol: 'admin', gym_id: 1 }
    expect(leerToken(tokenFalso(payload))).toMatchObject(payload)
  })

  // Los cuatro casos que dejaban la pantalla en blanco: cualquier basura en
  // localStorage tiene que resolverse en null, nunca en una excepción.
  it.each([
    ['null', null],
    ['undefined', undefined],
    ['cadena vacía', ''],
    ['texto suelto', 'abc'],
    ['sin las tres partes', 'solo.dos'],
    ['payload que no es base64', 'x.@@@no-base64@@@.z'],
    ['base64 que no es JSON', `x.${btoa('esto no es json')}.z`],
    ['JSON sin rol', `x.${btoa(JSON.stringify({ nombre: 'Ana' }))}.z`],
  ])('devuelve null ante %s', (_caso, valor) => {
    expect(leerToken(valor)).toBeNull()
  })

  it('no lanza excepción con ninguna entrada', () => {
    for (const v of [null, undefined, '', 'abc', 0, {}, []]) {
      expect(() => leerToken(v)).not.toThrow()
    }
  })
})
