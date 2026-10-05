(function () {
  var TOKEN_RE = /^[A-Za-z0-9_-]{8,80}$/;

  function apiBase() {
    var meta = document.querySelector('meta[name="api-base"]');
    var value = meta ? meta.getAttribute('content') || '' : '';
    return value.replace(/\/$/, '');
  }

  function postJson(path, body) {
    return fetch(apiBase() + path, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
      },
      body: JSON.stringify(body),
      credentials: 'same-origin',
    }).then(function (response) {
      return response.text().then(function (text) {
        var data = null;
        if (text) {
          try {
            data = JSON.parse(text);
          } catch (error) {
            data = null;
          }
        }
        return { ok: response.ok, status: response.status, data: data };
      });
    });
  }

  function getJson(path) {
    return fetch(apiBase() + path, {
      headers: { accept: 'application/json' },
      credentials: 'same-origin',
    }).then(function (response) {
      return response.text().then(function (text) {
        var data = null;
        if (text) {
          try {
            data = JSON.parse(text);
          } catch (error) {
            data = null;
          }
        }
        return { ok: response.ok, status: response.status, data: data };
      });
    });
  }

  function errorMessage(data, fallback) {
    if (data && data.error && typeof data.error.message === 'string' && data.error.message.trim()) {
      return data.error.message.trim();
    }
    return fallback;
  }

  function honeyFilled(form) {
    var field = form.querySelector('input[name="honeypot"]');
    return Boolean(field && field.value);
  }

  function turnstileToken(form) {
    var widget = form.querySelector('.cf-turnstile');
    if (!widget) return '';
    var input = form.querySelector('[name="cf-turnstile-response"]');
    var token = input && typeof input.value === 'string' ? input.value.trim() : '';
    if (!token && window.turnstile && typeof window.turnstile.getResponse === 'function') {
      try {
        token = String(window.turnstile.getResponse(widget) || '').trim();
      } catch (error) {
        token = '';
      }
    }
    return token;
  }

  function putTurnstile(form, body, status) {
    if (!form.querySelector('.cf-turnstile')) return true;
    var token = turnstileToken(form);
    if (!token) {
      if (status) status.textContent = 'Falta completar la verificación anti-bots.';
      return false;
    }
    body.turnstile_token = token;
    return true;
  }

  function formatClp(value) {
    if (value === null || value === undefined) return 'a cotizar';
    var number = Number(value);
    if (!Number.isFinite(number)) return 'a cotizar';
    return new Intl.NumberFormat('es-CL').format(number) + ' CLP';
  }

  function isHttp(url) {
    return typeof url === 'string' && /^https?:\/\//i.test(url);
  }

  function initDiagnostico() {
    var form = document.querySelector('#diagnostico');
    if (!form) return;
    var status = document.querySelector('#diagnostico-estado');
    var ok = document.querySelector('#diagnostico-ok');
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (form.dataset.busy === '1') return;
      if (honeyFilled(form)) {
        form.hidden = true;
        if (ok) ok.hidden = false;
        return;
      }
      var consent = form.querySelector('input[name="consent"]');
      if (!consent || !consent.checked) {
        if (status) status.textContent = 'Falta aceptar el texto de consentimiento.';
        return;
      }
      var body = {
        business: valueOf(form, 'business'),
        email: valueOf(form, 'email'),
        commune: valueOf(form, 'commune'),
        category: valueOf(form, 'category'),
        consent: true,
        consent_text: form.getAttribute('data-consent') || '',
      };
      var website = valueOf(form, 'website_url');
      if (website) body.website_url = website;
      var trap = form.querySelector('input[name="honeypot"]');
      body.honeypot = trap ? trap.value : '';
      if (!putTurnstile(form, body, status)) return;
      form.dataset.busy = '1';
      if (status) status.textContent = 'Enviando…';
      postJson('/api/public/diagnostico', body)
        .then(function (result) {
          if (result.status === 202 || result.ok) {
            form.hidden = true;
            if (ok) ok.hidden = false;
            if (status) status.textContent = '';
            return;
          }
          if (status) {
            status.textContent = errorMessage(
              result.data,
              'No pudimos enviar el formulario. No quedó una copia en este navegador.',
            );
          }
        })
        .catch(function () {
          if (status) {
            status.textContent =
              'No pudimos enviar el formulario. Revisa la conexión e inténtalo de nuevo.';
          }
        })
        .then(function () {
          form.dataset.busy = '0';
        });
    });
  }

  function valueOf(form, name) {
    var field = form.elements.namedItem(name);
    if (!field || typeof field.value !== 'string') return '';
    return field.value.trim();
  }

  function initDerechos() {
    var form = document.querySelector('#derechos-form');
    if (!form) return;
    var status = document.querySelector('#derechos-estado');
    var ok = document.querySelector('#derechos-ok');
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (form.dataset.busy === '1') return;
      if (honeyFilled(form)) {
        form.hidden = true;
        if (ok) ok.hidden = false;
        return;
      }
      var body = {
        kind: valueOf(form, 'kind'),
        email: valueOf(form, 'email'),
        details: valueOf(form, 'details'),
        honeypot: '',
      };
      if (!putTurnstile(form, body, status)) return;
      form.dataset.busy = '1';
      if (status) status.textContent = 'Enviando…';
      postJson('/api/public/derechos', body)
        .then(function (result) {
          if (result.status === 202 || result.ok) {
            form.hidden = true;
            if (ok) ok.hidden = false;
            if (status) status.textContent = '';
            return;
          }
          if (status) {
            status.textContent = errorMessage(
              result.data,
              'No pudimos registrar la solicitud. Inténtalo de nuevo.',
            );
          }
        })
        .catch(function () {
          if (status) status.textContent = 'No pudimos registrar la solicitud. Revisa la conexión.';
        })
        .then(function () {
          form.dataset.busy = '0';
        });
    });
  }

  function initBaja() {
    var form = document.querySelector('#baja-form');
    if (!form) return;
    var status = document.querySelector('#baja-estado');
    var ok = document.querySelector('#baja-ok');
    var input = form.querySelector('input[name="token"]');
    var fromLink = new URLSearchParams(location.search).get('token') || '';
    if (input && !input.value && TOKEN_RE.test(fromLink)) input.value = fromLink;
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (form.dataset.busy === '1') return;
      if (honeyFilled(form)) {
        form.hidden = true;
        if (ok) ok.hidden = false;
        return;
      }
      var token = valueOf(form, 'token');
      if (!TOKEN_RE.test(token)) {
        if (status) status.textContent = 'El token no tiene el formato del enlace de baja.';
        return;
      }
      var body = { token: token };
      if (!putTurnstile(form, body, status)) return;
      form.dataset.busy = '1';
      if (status) status.textContent = 'Enviando…';
      postJson('/api/public/baja', body)
        .then(function (result) {
          if (result.ok) {
            form.hidden = true;
            if (ok) ok.hidden = false;
            if (status) status.textContent = '';
            return;
          }
          if (status) {
            status.textContent = errorMessage(result.data, 'No pudimos registrar la baja.');
          }
        })
        .catch(function () {
          if (status) status.textContent = 'No pudimos registrar la baja. Revisa la conexión.';
        })
        .then(function () {
          form.dataset.busy = '0';
        });
    });
  }

  function initContacto() {
    var form = document.querySelector('#contacto-form');
    if (!form) return;
    var status = document.querySelector('#contacto-estado');
    var ok = document.querySelector('#contacto-ok');
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (form.dataset.busy === '1') return;
      if (honeyFilled(form)) {
        form.hidden = true;
        if (ok) ok.hidden = false;
        return;
      }
      var consent = form.querySelector('input[name="consent"]');
      if (!consent || !consent.checked) {
        if (status) status.textContent = 'Falta aceptar el texto de consentimiento.';
        return;
      }
      var body = {
        name: valueOf(form, 'name'),
        email: valueOf(form, 'email'),
        message: valueOf(form, 'message'),
        consent: true,
        honeypot: '',
      };
      var trap = form.querySelector('input[name="honeypot"]');
      body.honeypot = trap ? trap.value : '';
      if (!putTurnstile(form, body, status)) return;
      form.dataset.busy = '1';
      if (status) status.textContent = 'Enviando…';
      postJson('/api/public/contacto', body)
        .then(function (result) {
          if (result.status === 202 || result.ok) {
            form.hidden = true;
            if (ok) ok.hidden = false;
            if (status) status.textContent = '';
            return;
          }
          if (status) {
            status.textContent = errorMessage(
              result.data,
              'No pudimos enviar el mensaje. No quedó una copia en este navegador.',
            );
          }
        })
        .catch(function () {
          if (status) {
            status.textContent = 'No pudimos enviar el mensaje. Revisa la conexión e inténtalo de nuevo.';
          }
        })
        .then(function () {
          form.dataset.busy = '0';
        });
    });
  }

  function initCheckout() {
    var form = document.querySelector('#checkout');
    if (!form) return;
    var code = form.getAttribute('data-package') || '';
    var status = document.querySelector('#checkout-estado');
    var price = document.querySelector('[data-live-price]');
    getJson('/api/public/paquetes')
      .then(function (result) {
        if (!result.ok || !Array.isArray(result.data) || !price) return;
        var found = result.data.find(function (item) {
          return item && item.code === code;
        });
        if (!found) return;
        price.textContent = formatClp(found.price_clp);
      })
      .catch(function () {});

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (form.dataset.busy === '1') return;
      if (honeyFilled(form)) {
        if (status) status.textContent = 'No se envió el checkout.';
        return;
      }
      var terms = form.querySelector('input[name="terms"]');
      if (!terms || !terms.checked) {
        if (status) status.textContent = 'Falta confirmar que leíste los términos.';
        return;
      }
      var body = { package_code: code };
      var params = new URLSearchParams(location.search);
      var lead = params.get('lead_id') || '';
      if (/^[A-Za-z0-9_-]{1,80}$/.test(lead)) body.lead_id = lead;
      form.dataset.busy = '1';
      if (status) status.textContent = 'Creando el checkout…';
      postJson('/api/public/checkout', body)
        .then(function (result) {
          var url = result.data && result.data.checkout_url;
          if (result.ok && isHttp(url)) {
            if (status) status.textContent = 'Te estamos llevando al checkout del proveedor.';
            location.assign(url);
            return;
          }
          if (status) {
            status.textContent = result.ok
              ? 'La API no entregó un enlace de pago. No se hizo ningún cobro.'
              : errorMessage(result.data, 'No se pudo crear el checkout. No se hizo ningún cobro.');
          }
          form.dataset.busy = '0';
        })
        .catch(function () {
          if (status) status.textContent = 'No se pudo crear el checkout. No se hizo ningún cobro.';
          form.dataset.busy = '0';
        });
    });
  }

  function initPaquetes() {
    var table = document.querySelector('[data-packages]');
    if (!table) return;
    var status = document.querySelector('#paquetes-estado');
    getJson('/api/public/paquetes')
      .then(function (result) {
        if (!result.ok || !Array.isArray(result.data)) {
          if (status) {
            status.textContent =
              'No se pudo leer la API. Se muestran los precios publicados por defecto.';
          }
          return;
        }
        result.data.forEach(function (item) {
          if (!item || typeof item.code !== 'string') return;
          if (!/^[a-z0-9_]+$/.test(item.code)) return;
          var row = table.querySelector('[data-package-row="' + item.code + '"]');
          if (!row) return;
          var priceCell = row.querySelector('[data-package-price]');
          if (priceCell) priceCell.textContent = formatClp(item.price_clp);
          var nameCell = row.querySelector('[data-package-name]');
          if (nameCell && typeof item.name === 'string' && item.name.trim()) {
            nameCell.textContent = item.name.trim();
          }
          var list = row.querySelector('[data-package-includes]');
          if (list && Array.isArray(item.includes)) {
            list.replaceChildren();
            item.includes.forEach(function (line) {
              if (typeof line !== 'string') return;
              var li = document.createElement('li');
              li.textContent = line;
              list.appendChild(li);
            });
          }
        });
        if (status) status.textContent = 'Tabla actualizada desde la API.';
      })
      .catch(function () {
        if (status) {
          status.textContent =
            'No se pudo leer la API. Se muestran los precios publicados por defecto.';
        }
      });
  }

  function projectToken() {
    var match = location.pathname.match(/^\/proyecto\/([^/]+)\/?$/);
    if (!match) return '';
    var token = '';
    try {
      token = decodeURIComponent(match[1]);
    } catch (error) {
      return '';
    }
    if (token === 'shell') {
      var query = new URLSearchParams(location.search).get('token') || '';
      token = query;
    }
    if (!TOKEN_RE.test(token)) return '';
    return token;
  }

  function initPortal() {
    var root = document.querySelector('#portal');
    if (!root) return;
    var status = document.querySelector('#portal-estado');
    var actions = document.querySelector('#portal-acciones');
    var token = projectToken();
    if (!token) {
      if (status) {
        status.textContent =
          'Este enlace no trae el token del proyecto. Ábrelo como /proyecto/ seguido del token que te enviamos.';
      }
      return;
    }

    var path = '/api/public/proyecto/' + encodeURIComponent(token);
    getJson(path)
      .then(function (result) {
        if (!result.ok || !result.data) {
          if (status) {
            status.textContent =
              result.status === 404
                ? 'No encontramos un proyecto con este token.'
                : errorMessage(result.data, 'No pudimos leer el proyecto.');
          }
          return;
        }
        renderProject(result.data);
        if (actions) actions.disabled = false;
        bindPortal(path);
      })
      .catch(function () {
        if (status) status.textContent = 'No pudimos leer el proyecto. Revisa la conexión.';
      });
  }

  function renderProject(data) {
    var status = document.querySelector('#portal-estado');
    var business = document.querySelector('#portal-negocio');
    var revisions = document.querySelector('#portal-revisiones');
    var preview = document.querySelector('#portal-preview');
    var labels = {
      pagado: 'Pagado. Falta el intake para producir.',
      en_produccion: 'En producción.',
      en_revision_cliente: 'En revisión tuya. Puedes comentar o aprobar.',
      entregado: 'Entregado.',
      postventa: 'Entregado, en seguimiento.',
      revision: 'En revisión interna.',
    };
    var code = typeof data.status === 'string' ? data.status : '';
    if (status) {
      status.textContent = labels[code] || (code ? 'Estado informado por la API: ' + code : 'Sin estado.');
    }
    if (business) {
      business.textContent =
        typeof data.business === 'string' && data.business.trim()
          ? 'Negocio: ' + data.business.trim()
          : 'La API no informó el nombre del negocio.';
    }
    if (revisions) {
      var used = Number(data.revisions_used);
      var max = Number(data.max_revisions);
      revisions.textContent =
        Number.isFinite(used) && Number.isFinite(max)
          ? 'Revisiones usadas: ' + used + ' de ' + max + '.'
          : 'La API no informó las revisiones.';
    }
    if (preview) {
      preview.replaceChildren();
      if (isHttp(data.preview_url)) {
        var link = document.createElement('a');
        link.href = data.preview_url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Abrir vista previa';
        preview.appendChild(link);
      } else {
        preview.textContent = 'Todavía no hay una vista previa. No mostramos un sitio de ejemplo.';
      }
    }
  }

  function bindPortal(path) {
    var intake = document.querySelector('#intake');
    var feedback = document.querySelector('#feedback');
    var approve = document.querySelector('#aprobar');
    var status = document.querySelector('#portal-estado');

    if (intake) {
      intake.addEventListener('submit', function (event) {
        event.preventDefault();
        if (honeyFilled(intake)) return;
        var payload = {};
        ['address', 'phone', 'hours', 'services', 'domain', 'logo_url', 'photos_note'].forEach(
          function (name) {
            var fieldValue = valueOf(intake, name);
            if (fieldValue) payload[name] = fieldValue;
          },
        );
        if (!payload.services || (!payload.phone && !payload.address)) {
          if (status) {
            status.textContent = 'Indica los servicios y, además, un teléfono o una dirección.';
          }
          return;
        }
        postJson(path + '/intake', payload)
          .then(function (result) {
            if (status) {
              status.textContent = result.ok
                ? 'Guardamos el intake.'
                : errorMessage(result.data, 'No pudimos guardar el intake.');
            }
          })
          .catch(function () {
            if (status) status.textContent = 'No pudimos guardar el intake.';
          });
      });
    }

    if (feedback) {
      feedback.addEventListener('submit', function (event) {
        event.preventDefault();
        if (honeyFilled(feedback)) return;
        var text = valueOf(feedback, 'text');
        if (!text) {
          if (status) status.textContent = 'Escribe el comentario de esta ronda.';
          return;
        }
        postJson(path + '/feedback', { text: text })
          .then(function (result) {
            if (status) {
              status.textContent =
                result.status === 202 || result.ok
                  ? 'Registramos la ronda de comentarios.'
                  : errorMessage(result.data, 'No pudimos registrar el comentario.');
            }
            if (result.ok || result.status === 202) feedback.reset();
          })
          .catch(function () {
            if (status) status.textContent = 'No pudimos registrar el comentario.';
          });
      });
    }

    if (approve) {
      approve.addEventListener('click', function () {
        if (
          !window.confirm(
            '¿Apruebas esta vista previa para publicar? Desde esta página no se puede deshacer.',
          )
        ) {
          return;
        }
        postJson(path + '/aprobar', {})
          .then(function (result) {
            if (status) {
              status.textContent = result.ok
                ? 'Quedó aprobada. El saldo, si corresponde, se cobra antes de publicar.'
                : errorMessage(result.data, 'No pudimos aprobar el proyecto.');
            }
          })
          .catch(function () {
            if (status) status.textContent = 'No pudimos aprobar el proyecto.';
          });
      });
    }
  }

  function initPagoRetorno() {
    var slot = document.querySelector('#pago-retorno');
    if (!slot) return;
    var params = new URLSearchParams(location.search);
    var status = params.get('status') || '';
    var payment = params.get('payment_id') || params.get('collection_id') || '';
    var safeStatus = /^[A-Za-z0-9_-]{1,40}$/.test(status) ? status : '';
    var safePayment = /^[A-Za-z0-9_-]{1,80}$/.test(payment) ? payment : '';
    if (!safeStatus && !safePayment) return;
    slot.hidden = false;
    slot.replaceChildren();
    function row(title, value) {
      var wrap = document.createElement('div');
      var dt = document.createElement('dt');
      dt.textContent = title;
      var dd = document.createElement('dd');
      dd.textContent = value;
      wrap.append(dt, dd);
      return wrap;
    }
    slot.append(row('Dato de retorno, no verificado', safeStatus || 'sin estado'));
    if (safePayment) slot.append(row('Identificador informado por el retorno', safePayment));
  }

  initDiagnostico();
  initContacto();
  initDerechos();
  initBaja();
  initCheckout();
  initPaquetes();
  initPortal();
  initPagoRetorno();
})();
