// Contraseñas de prueba generadas en cada corrida: nunca se escriben a mano en los specs.
import { randomBytes, randomInt } from 'node:crypto';

const LETRAS = 'ABCDEFGHJKLMNPQRSTUVWXYZ';

/** Contraseña aleatoria que cumple validar_password_fuerte (letras y números, 8+). */
export function claveDePrueba() {
  return randomBytes(8).toString('hex')
    + LETRAS[randomInt(LETRAS.length)]
    + String(randomInt(10));
}
