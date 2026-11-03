/* ── Sesión AMICANA ─────────────────────────────────────────────
   La sesión vive en una cookie httpOnly (`amicana_session`) que el navegador
   manda solo. Este módulo NO guarda ni lee el JWT: el rol y el nombre salen
   de /auth/me, y los métodos que modifican datos llevan el header
   X-CSRF-Token con el valor de la cookie `amicana_csrf`. */
(function () {
    'use strict';

    var LOGIN_URL = 'index.html';
    var METODOS_SEGUROS = ['GET', 'HEAD', 'OPTIONS'];
    /* Pedidos de autenticación: un 401 acá es parte del flujo, no una sesión vencida. */
    var SIN_REDIRECCION = ['/login', '/auth/login', '/auth/register', '/auth/me', '/auth/logout'];

    function leerCookie(nombre) {
        var partes = document.cookie ? document.cookie.split('; ') : [];
        for (var i = 0; i < partes.length; i++) {
            var idx = partes[i].indexOf('=');
            if (idx > 0 && partes[i].slice(0, idx) === nombre) {
                return decodeURIComponent(partes[i].slice(idx + 1));
            }
        }
        return null;
    }

    function esPaginaLogin() {
        var p = window.location.pathname;
        return /\/index\.html$/.test(p) || /\/$/.test(p);
    }

    function irALogin() {
        if (!esPaginaLogin()) window.location.href = LOGIN_URL;
    }

    function pathDe(url) {
        try { return new URL(url, window.location.href).pathname; }
        catch (_) { return String(url); }
    }

    /* Devuelve el usuario de /auth/me o null si no hay sesión válida. */
    async function obtenerSesion() {
        try {
            var res = await fetch('/auth/me', { credentials: 'same-origin' });
            if (!res.ok) return null;
            return await res.json();
        } catch (_) {
            return null;
        }
    }

    /* fetch same-origin con CSRF en métodos inseguros; 401 → pantalla de login. */
    async function apiFetch(url, opts) {
        opts = Object.assign({}, opts);
        opts.credentials = 'same-origin';
        var metodo = (opts.method || 'GET').toUpperCase();
        var headers = Object.assign({}, opts.headers);
        if (METODOS_SEGUROS.indexOf(metodo) === -1) {
            var csrf = leerCookie('amicana_csrf');
            if (csrf) headers['X-CSRF-Token'] = csrf;
        }
        opts.headers = headers;

        var res = await fetch(url, opts);
        if (res.status === 401) {
            var path = pathDe(url);
            if (SIN_REDIRECCION.indexOf(path) === -1) irALogin();
        }
        return res;
    }

    async function cerrarSesion() {
        var ok = false;
        try {
            var res = await apiFetch('/auth/logout', { method: 'POST' });
            ok = res.ok;
        } catch (_) { /* sin red: se trata como fallo */ }
        if (!ok) {
            /* La sesión sigue activa en el servidor: no mostramos el login como si se hubiera cerrado. */
            window.alert('No se pudo cerrar la sesión. Intentá de nuevo.');
            return;
        }
        try {
            sessionStorage.removeItem('gp_perfil_omitido');
            localStorage.removeItem('amicana_chat_session'); /* el chat no pasa de un usuario al siguiente */
        } catch (_) { /* storage no disponible */ }
        window.location.href = LOGIN_URL;
    }

    window.leerCookie = leerCookie;
    window.obtenerSesion = obtenerSesion;
    window.apiFetch = apiFetch;
    window.cerrarSesion = cerrarSesion;
})();
