/* =====================================================================
   CenterMedical · Portal de Pacientes
   JS común del panel (cargado desde panel_base.html, requiere jQuery).
   ===================================================================== */

/* ---------- Toast ---------- */
let toastTimer = null;

// type: 'success' (por defecto) | 'error'
function showToast(msg, type) {
    const toast = document.getElementById('toastNotification');
    if (!toast) return;
    const icon = document.getElementById('toastIcon');
    document.getElementById('toastMsg').textContent = msg;

    const isError = type === 'error';
    toast.classList.toggle('toast-error', isError);
    icon.className = 'toast-icon fa-solid ' + (isError ? 'fa-circle-exclamation' : 'fa-circle-check');

    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('is-visible'); }, 3500);
}

/* ---------- Utilidades ---------- */
// Escapa texto antes de inyectarlo como HTML
function escapeHtml(value) {
    return String(value === null || value === undefined ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getCsrf() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

// POST a /panel. Acepta un objeto plano (los arrays se envían como claves repetidas) o un FormData.
function postAction(data) {
    const isFormData = (typeof FormData !== 'undefined') && data instanceof FormData;
    if (isFormData) {
        if (!data.has('csrfmiddlewaretoken')) data.append('csrfmiddlewaretoken', getCsrf());
    } else {
        data = Object.assign({csrfmiddlewaretoken: getCsrf()}, data);
    }
    return $.ajax({
        url: '/panel',
        type: 'POST',
        data: data,
        dataType: 'json',
        traditional: true,   // listas como days=1&days=2 (request.POST.getlist)
        processData: !isFormData,
        contentType: isFormData ? false : 'application/x-www-form-urlencoded; charset=UTF-8',
        headers: {'X-CSRFToken': getCsrf()}
    });
}

// Muestra u oculta un .form-hint con su texto (<span> interno)
function setHint(el, msg) {
    if (!el) return;
    if (msg) {
        el.querySelector('span').textContent = msg;
        el.hidden = false;
    } else {
        el.hidden = true;
    }
}

// Estado de "cargando" en un botón con <span> de texto
function setButtonLoading(btn, loading, text) {
    const label = btn.querySelector('span') || btn;
    if (loading) {
        btn.dataset.originalText = label.textContent;
        label.textContent = text || 'Procesando...';
        btn.disabled = true;
    } else {
        if (btn.dataset.originalText) label.textContent = btn.dataset.originalText;
        btn.disabled = false;
    }
}

// Recarga la página actual mostrando un mensaje con ?info=
function reloadWithInfo(msg) {
    const url = new URL(window.location.href);
    if (msg) url.searchParams.set('info', msg); else url.searchParams.delete('info');
    window.location.href = url.toString();
}

/* ---------- Horas y franjas ---------- */
// "HH:MM" → minutos desde medianoche (NaN si no es válido)
function timeToMinutes(value) {
    const m = /^(\d{1,2}):(\d{2})/.exec(value || '');
    if (!m) return NaN;
    const h = Number(m[1]), min = Number(m[2]);
    return (h > 23 || min > 59) ? NaN : h * 60 + min;
}

function minutesToTime(total) {
    const h = Math.floor(total / 60), m = total % 60;
    return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
}

/* Horas de inicio de cada turno entre start y end ("HH:MM") cada `minutes`.
   Misma regla que el backend: un turno entra solo si inicio + duración ≤ fin. */
function buildSlotTimes(start, end, minutes) {
    const from = timeToMinutes(start), to = timeToMinutes(end), step = Number(minutes);
    const times = [];
    if (isNaN(from) || isNaN(to) || !(step > 0) || from >= to) return times;
    for (let t = from; t + step <= to; t += step) times.push(minutesToTime(t));
    return times;
}

/* ---------- Fotos ---------- */
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

// Devuelve un mensaje de error o '' si la foto es válida (o no hay foto)
function validatePhoto(file) {
    if (!file) return '';
    if (PHOTO_TYPES.indexOf(file.type) === -1) return 'La fotografía debe ser JPG, PNG o WEBP.';
    if (file.size > MAX_PHOTO_BYTES) return 'La fotografía no debe superar los 5 MB.';
    return '';
}

// Muestra en `img` la vista previa del archivo elegido en `input`
function bindPhotoPreview(input, img) {
    const original = img.src;
    input.addEventListener('change', function () {
        const file = input.files[0];
        const error = validatePhoto(file);
        if (error) {
            showToast(error, 'error');
            input.value = '';
            img.src = original;
            return;
        }
        img.src = file ? URL.createObjectURL(file) : original;
    });
}

/* ---------- Modales (.modal-backdrop) ---------- */
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('is-open');
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('is-open');
}

document.addEventListener('click', function (e) {
    const closer = e.target.closest('[data-modal-close]');
    if (closer) {
        closer.closest('.modal-backdrop').classList.remove('is-open');
    } else if (e.target.classList.contains('modal-backdrop') && e.target.dataset.dismissible !== 'false') {
        e.target.classList.remove('is-open');
    }
});

document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('.modal-backdrop.is-open').forEach(function (m) {
        if (m.dataset.dismissible !== 'false') m.classList.remove('is-open');
    });
});

/* ---------- Selector de fecha (flatpickr) + turnos ----------
   Compartido por Reservar Cita y Reagendar. */
const SlotPicker = (function () {
    function fetchDates(doctorId) {
        return $.getJSON('/panel', {action: 'getdatesavalies', doctor_id: doctorId});
    }

    function fetchSlots(doctorId, date) {
        return $.getJSON('/panel', {action: 'getslots', doctor_id: doctorId, date: date});
    }

    // Crea (o recrea) el flatpickr habilitando solo las fechas recibidas
    function initDatePicker(input, dates, onChange) {
        destroyDatePicker(input);
        input.disabled = false;
        return flatpickr(input, {
            locale: (window.flatpickr && flatpickr.l10ns && flatpickr.l10ns.es) ? 'es' : 'default',
            dateFormat: 'Y-m-d',
            altInput: true,
            altFormat: 'j \\d\\e F \\d\\e Y',
            altInputClass: input.className,
            disableMobile: true,
            enable: dates,
            onChange: function (selected, dateStr) { onChange(dateStr); }
        });
    }

    function destroyDatePicker(input) {
        if (input._flatpickr) input._flatpickr.destroy();
        input.value = '';
    }

    function renderMessage(container, msg, icon) {
        container.innerHTML =
            '<p class="slots-message"><i class="fa-solid ' + (icon || 'fa-circle-info') + ' text-[10px]"></i>' +
            escapeHtml(msg) + '</p>';
    }

    function renderLoading(container) {
        renderMessage(container, 'Cargando turnos...', 'fa-spinner fa-spin');
    }

    // Pinta los turnos como botones .time-btn; onSelect(time) al elegir uno
    function renderSlots(container, slots, onSelect) {
        container.innerHTML = '';
        slots.forEach(function (slot) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'time-btn';
            btn.dataset.time = slot.time;
            btn.textContent = slot.label || slot.time;
            btn.addEventListener('click', function () {
                container.querySelectorAll('.time-btn').forEach(function (b) { b.classList.remove('is-active'); });
                btn.classList.add('is-active');
                onSelect(slot.time);
            });
            container.appendChild(btn);
        });
    }

    /* Controlador completo fecha → turnos.
       opts: {dateInput, slotsBox, dateHint, onChange(state)}
       state: {date, time} */
    function create(opts) {
        let doctorId = null;
        let datesReq = 0;
        let slotsReq = 0;
        const state = {date: '', time: ''};

        function notify() { if (opts.onChange) opts.onChange(state); }

        function resetSlots(msg) {
            slotsReq++;
            state.time = '';
            renderMessage(opts.slotsBox, msg || 'Selecciona una fecha para ver los turnos.');
        }

        function reset(placeholder) {
            datesReq++;
            doctorId = null;
            state.date = '';
            destroyDatePicker(opts.dateInput);
            opts.dateInput.disabled = true;
            opts.dateInput.placeholder = placeholder || 'Selecciona un médico primero';
            setHint(opts.dateHint, '');
            resetSlots();
            notify();
        }

        function loadSlots(date) {
            resetSlots();
            state.date = date || '';
            notify();
            if (!date || !doctorId) return;
            const token = slotsReq;
            renderLoading(opts.slotsBox);
            fetchSlots(doctorId, date)
                .done(function (response) {
                    if (token !== slotsReq) return;
                    const slots = (response && response.data) || [];
                    if (!slots.length) {
                        renderMessage(opts.slotsBox, 'No hay turnos disponibles para esta fecha.', 'fa-calendar-xmark');
                        return;
                    }
                    renderSlots(opts.slotsBox, slots, function (time) {
                        state.time = time;
                        notify();
                    });
                })
                .fail(function () {
                    if (token !== slotsReq) return;
                    renderMessage(opts.slotsBox, 'No se pudieron cargar los turnos.', 'fa-triangle-exclamation');
                });
        }

        function load(newDoctorId) {
            reset('Cargando fechas...');
            doctorId = newDoctorId;
            const token = datesReq;
            fetchDates(newDoctorId)
                .done(function (response) {
                    if (token !== datesReq) return;
                    const dates = (response && response.data) || [];
                    if (!dates.length) {
                        opts.dateInput.placeholder = 'Sin fechas disponibles';
                        setHint(opts.dateHint, 'El médico no tiene fechas disponibles por el momento.');
                        resetSlots('No hay turnos disponibles.');
                        return;
                    }
                    opts.dateInput.placeholder = 'Selecciona una fecha';
                    initDatePicker(opts.dateInput, dates, loadSlots);
                })
                .fail(function () {
                    if (token !== datesReq) return;
                    opts.dateInput.placeholder = 'Sin fechas disponibles';
                    setHint(opts.dateHint, 'No se pudieron cargar las fechas disponibles.');
                });
        }

        return {
            load: load,
            reset: reset,
            reloadSlots: function () { loadSlots(state.date); },
            state: state
        };
    }

    return {create: create, renderMessage: renderMessage};
})();

/* ---------- Layout: sidebar y mensajes por querystring ---------- */
document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('toggleSidebar');
    const isDesktop = function () { return window.matchMedia('(min-width: 1024px)').matches; };

    function closeMobile() {
        sidebar.classList.remove('is-open');
        overlay.hidden = true;
    }

    if (sidebar && toggle) {
        toggle.addEventListener('click', function () {
            if (isDesktop()) {
                sidebar.classList.toggle('is-collapsed');
            } else {
                const opening = !sidebar.classList.contains('is-open');
                sidebar.classList.toggle('is-open', opening);
                overlay.hidden = !opening;
            }
        });
        overlay.addEventListener('click', closeMobile);
        const closer = document.getElementById('closeSidebar');
        if (closer) closer.addEventListener('click', closeMobile);
    }

    const url = new URL(window.location.href);
    const info = url.searchParams.get('info');
    if (info) {
        showToast(info);
        // Evita que el mensaje reaparezca al recargar
        url.searchParams.delete('info');
        window.history.replaceState(null, '', url.toString());
    }
});

/* ---------- Cancelación de citas (partial cancel_modal.html) ----------
   Botones: <button class="js-cancel-appointment" data-id data-cancel-action
            data-reason-required="1|0" data-label="...">                     */
function bindCancelButtons() {
    const modal = document.getElementById('cancelModal');
    if (!modal) return;
    const form = document.getElementById('cancelForm');
    const reason = document.getElementById('cancelReason');
    const alertBox = document.getElementById('cancelAlert');
    const submitBtn = document.getElementById('cancelSubmit');
    let current = null;

    document.querySelectorAll('.js-cancel-appointment').forEach(function (btn) {
        btn.addEventListener('click', function () {
            current = {
                id: btn.dataset.id,
                action: btn.dataset.cancelAction || 'cancelappointment',
                required: btn.dataset.reasonRequired === '1'
            };
            form.reset();
            setHint(alertBox, '');
            reason.required = current.required;
            document.getElementById('cancelReasonRequired').hidden = !current.required;
            document.getElementById('cancelReasonOptional').hidden = current.required;
            document.getElementById('cancelModalLabel').textContent = btn.dataset.label || 'Se cancelará la cita';
            openModal('cancelModal');
            reason.focus();
        });
    });

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!current) return;
        const text = reason.value.trim();
        if (current.required && !text) return setHint(alertBox, 'Indica el motivo de la cancelación.');
        setHint(alertBox, '');
        setButtonLoading(submitBtn, true, 'Cancelando...');
        postAction({action: current.action, id: current.id, reason: text})
            .done(function (response) {
                if (response && response.result === 'ok') {
                    reloadWithInfo(response.mensaje || 'Cita cancelada correctamente.');
                } else {
                    setHint(alertBox, (response && response.mensaje) || 'No se pudo cancelar la cita.');
                    setButtonLoading(submitBtn, false);
                }
            })
            .fail(function () {
                setHint(alertBox, 'Error de conexión al cancelar la cita.');
                setButtonLoading(submitBtn, false);
            });
    });
}

/* ---------- Confirmar cita (médico) ----------
   Botones: <button class="js-confirm" data-id [data-confirm-action]><span>Confirmar</span></button> */
function bindConfirmButtons() {
    document.querySelectorAll('.js-confirm').forEach(function (btn) {
        btn.addEventListener('click', function () {
            setButtonLoading(btn, true, 'Confirmando...');
            postAction({action: btn.dataset.confirmAction || 'confirmappointment', id: btn.dataset.id})
                .done(function (response) {
                    if (response && response.result === 'ok') {
                        reloadWithInfo(response.mensaje || 'Cita confirmada.');
                    } else {
                        showToast((response && response.mensaje) || 'No se pudo confirmar la cita.', 'error');
                        setButtonLoading(btn, false);
                    }
                })
                .fail(function () {
                    showToast('Error de conexión al confirmar la cita.', 'error');
                    setButtonLoading(btn, false);
                });
        });
    });
}

/* ---------- Filtro de fecha libre (flatpickr) ---------- */
function initDateFilter(input) {
    if (!input || !window.flatpickr) return null;
    return flatpickr(input, {
        locale: (flatpickr.l10ns && flatpickr.l10ns.es) ? 'es' : 'default',
        dateFormat: 'Y-m-d',
        altInput: true,
        altFormat: 'd/m/Y',
        altInputClass: input.className,
        disableMobile: true,
        allowInput: false
    });
}

/* ---------- Editor de medicamentos (partial medication_editor.html) ----------
   const editor = MedicationEditor.create({container, template, addButton, emptyEl, initial});
   editor.validate() → '' o mensaje · editor.serialize() → string JSON (siempre, '[]' si vacío)
   editor.highlight(n) resalta la fila n (base 1) · editor.highlightFromMessage(msg)          */
const MedicationEditor = (function () {
    const MAX_ROWS = 30;
    const OTHER = '__other__';
    const REQUIRED = {name: 'el nombre', dose: 'la dosis', frequency: 'la frecuencia'};

    function create(opts) {
        const container = opts.container;
        const template = opts.template;

        function rows() { return Array.prototype.slice.call(container.querySelectorAll('.med-row')); }
        function field(row, name) { return row.querySelector('[data-field="' + name + '"]'); }

        function refresh() {
            const count = rows().length;
            if (opts.emptyEl) opts.emptyEl.hidden = count > 0;
            if (opts.addButton) opts.addButton.disabled = count >= MAX_ROWS;
        }

        function clearErrors(row) {
            row.classList.remove('has-error');
            row.querySelectorAll('.is-invalid').forEach(function (el) { el.classList.remove('is-invalid'); });
        }

        function setFrequency(row, value) {
            const preset = field(row, 'frequency_preset');
            const other = field(row, 'frequency_other');
            const isPreset = !value || Array.prototype.some.call(preset.options, function (o) {
                return o.value !== OTHER && o.value === value;
            });
            preset.value = isPreset ? (value || '') : OTHER;
            other.value = isPreset ? '' : value;
            other.hidden = isPreset;
        }

        function getFrequency(row) {
            const preset = field(row, 'frequency_preset').value;
            return preset === OTHER ? field(row, 'frequency_other').value.trim() : preset;
        }

        function addRow(data) {
            if (rows().length >= MAX_ROWS) {
                showToast('No se pueden prescribir más de ' + MAX_ROWS + ' medicamentos.', 'error');
                return null;
            }
            data = data || {};
            const row = template.content.firstElementChild.cloneNode(true);
            ['name', 'dose', 'duration', 'instructions'].forEach(function (k) { field(row, k).value = data[k] || ''; });
            const route = field(row, 'route');
            route.value = data.route || '';
            if (data.route && route.value !== data.route) {   // vía no listada
                route.appendChild(new Option(data.route, data.route, true, true));
            }
            setFrequency(row, data.frequency || '');

            field(row, 'frequency_preset').addEventListener('change', function (e) {
                const other = field(row, 'frequency_other');
                other.hidden = e.target.value !== OTHER;
                if (!other.hidden) other.focus();
            });
            row.addEventListener('input', function () { clearErrors(row); });
            row.addEventListener('change', function () { clearErrors(row); });
            row.querySelector('[data-med-remove]').addEventListener('click', function () {
                row.remove();
                refresh();
            });
            container.appendChild(row);
            refresh();
            return row;
        }

        function highlight(n) {
            const row = rows()[n - 1];
            if (!row) return;
            row.classList.add('has-error');
            row.scrollIntoView({behavior: 'smooth', block: 'center'});
        }

        function validate() {
            let message = '';
            rows().forEach(function (row, i) {
                clearErrors(row);
                const missing = [];
                if (!field(row, 'name').value.trim()) missing.push('name');
                if (!field(row, 'dose').value.trim()) missing.push('dose');
                if (!getFrequency(row)) missing.push('frequency');
                if (!missing.length) return;
                row.classList.add('has-error');
                missing.forEach(function (k) {
                    let el = field(row, k);
                    if (k === 'frequency') {
                        el = field(row, 'frequency_preset').value === OTHER ? field(row, 'frequency_other') : field(row, 'frequency_preset');
                    }
                    el.classList.add('is-invalid');
                });
                if (!message) {
                    message = 'Medicamento ' + (i + 1) + ': falta ' + REQUIRED[missing[0]] + '.';
                    row.scrollIntoView({behavior: 'smooth', block: 'center'});
                }
            });
            return message;
        }

        function serialize() {
            return JSON.stringify(rows().map(function (row) {
                return {
                    name: field(row, 'name').value.trim(),
                    dose: field(row, 'dose').value.trim(),
                    frequency: getFrequency(row),
                    duration: field(row, 'duration').value.trim(),
                    route: field(row, 'route').value,
                    instructions: field(row, 'instructions').value.trim()
                };
            }));
        }

        if (opts.addButton) {
            opts.addButton.addEventListener('click', function () {
                const row = addRow();
                if (row) field(row, 'name').focus();
            });
        }
        (opts.initial || []).forEach(function (m) { addRow(m); });
        refresh();

        return {
            addRow: addRow,
            validate: validate,
            serialize: serialize,
            highlight: highlight,
            highlightFromMessage: function (msg) {
                const m = /Medicamento\s+(\d+)/i.exec(msg || '');
                if (m) highlight(Number(m[1]));
            },
            count: function () { return rows().length; }
        };
    }

    // Lee el JSON de <script type="application/json" id="...">
    function readInitial(id) {
        const el = document.getElementById(id);
        if (!el) return [];
        try { return JSON.parse(el.textContent) || []; } catch (e) { return []; }
    }

    return {create: create, readInitial: readInitial};
})();

/* ---------- Agenda del médico: resalta la próxima cita pendiente ----------
   Tarjetas con data-when="YYYY-MM-DDTHH:MM" y data-next-candidate="1". */
function highlightNextAppointment(root) {
    const now = new Date();
    const cards = Array.prototype.slice.call((root || document).querySelectorAll('[data-next-candidate="1"]'));
    let next = null;
    cards.forEach(function (card) {
        const when = new Date(card.dataset.when);
        if (isNaN(when) || when < now) return;
        if (!next || when < new Date(next.dataset.when)) next = card;
    });
    if (!next) return;
    next.classList.add('appt-next');
    const flag = next.querySelector('[data-next-flag]');
    if (flag) flag.hidden = false;
}

/* ---------- Selects encadenados (país → provincia → cantón → parroquia) ----------
   bindCascadeSelects([
       {select: countryEl},
       {select: provinceEl, action: 'getprovinces', param: 'country_id', placeholder: '-- Provincia --'},
       ...
   ]);
   Al cambiar el nivel i se vacían los inferiores y se carga el nivel i+1 vía GET {results:[{id,text}]}. */
function bindCascadeSelects(levels) {
    function reset(level, text) {
        level.select.innerHTML = '';
        level.select.appendChild(new Option(text || level.placeholder || '-- Seleccionar --', ''));
        level.select.disabled = true;
    }

    levels.forEach(function (level, i) {
        const next = levels[i + 1];
        if (!next) return;
        if (!level.select.value) next.select.disabled = true;
        level.select.addEventListener('change', function () {
            for (let j = i + 1; j < levels.length; j++) reset(levels[j]);
            if (!level.select.value) return;
            next.token = (next.token || 0) + 1;
            const token = next.token;
            reset(next, 'Cargando...');
            const params = {action: next.action};
            params[next.param] = level.select.value;
            $.getJSON('/panel', params)
                .done(function (response) {
                    if (token !== next.token) return;
                    const results = (response && response.results) || [];
                    reset(next);
                    results.forEach(function (item) { next.select.appendChild(new Option(item.text, item.id)); });
                    next.select.disabled = !results.length;
                    if (!results.length) next.select.options[0].textContent = 'Sin opciones disponibles';
                })
                .fail(function () {
                    if (token !== next.token) return;
                    reset(next);
                    showToast('No se pudieron cargar las opciones.', 'error');
                });
        });
    });
}

/* ---------- Cálculos en vivo ---------- */
// Edad en años cumplidos desde "YYYY-MM-DD" (null si no es válida o es futura)
function calcAge(dateStr) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr || '');
    if (!m) return null;
    const birth = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    const today = new Date();
    if (birth > today) return null;
    let age = today.getFullYear() - birth.getFullYear();
    const beforeBirthday = today.getMonth() < birth.getMonth() ||
        (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
    if (beforeBirthday) age--;
    return age;
}

// IMC a partir de peso (kg) y talla (cm). Devuelve {value, label, tone} o null.
function calcBMI(weightKg, heightCm) {
    const w = parseFloat(String(weightKg).replace(',', '.'));
    const h = parseFloat(String(heightCm).replace(',', '.')) / 100;
    if (!(w > 0) || !(h > 0)) return null;
    const value = w / (h * h);
    if (!isFinite(value)) return null;
    let label = 'Normal', tone = 'normal';
    if (value < 18.5) { label = 'Bajo peso'; tone = 'warning'; }
    else if (value >= 30) { label = 'Obesidad'; tone = 'danger'; }
    else if (value >= 25) { label = 'Sobrepeso'; tone = 'warning'; }
    return {value: Math.round(value * 10) / 10, label: label, tone: tone};
}

/* ---------- Validación de formularios por campo ---------- */
function isValidEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(String(value || '').trim());
}

function clearFieldErrors(form) {
    form.querySelectorAll('.is-invalid').forEach(function (el) { el.classList.remove('is-invalid'); });
    form.querySelectorAll('.field-error').forEach(function (el) { el.remove(); });
}

// Marca el campo `name` del formulario con un mensaje debajo
function markFieldError(form, name, msg) {
    const input = form.querySelector('[name="' + name + '"]') || form.querySelector('#' + CSS.escape(name));
    if (!input) return;
    const target = (input._flatpickr && input._flatpickr.altInput) || input;
    target.classList.add('is-invalid');
    if (input.type === 'checkbox' && input.name) {
        form.querySelectorAll('[name="' + input.name + '"]').forEach(function (el) { el.classList.add('is-invalid'); });
    }
    // En checkbox/radio (chips, tarjetas) el mensaje va en el toast: no romper el selector input + span
    if (msg && input.type !== 'checkbox' && input.type !== 'radio') {
        const holder = target.closest('.select-wrap') || target;
        const err = document.createElement('span');
        err.className = 'field-error';
        err.textContent = msg;
        holder.insertAdjacentElement('afterend', err);
    }
}

// Marca el campo cuyo data-error-keys aparece antes en el mensaje del backend
// (ante empate de posición gana la clave más larga: "correo institucional" > "correo")
function markErrorFromMessage(form, msg) {
    const text = String(msg || '').toLowerCase();
    let best = null;
    form.querySelectorAll('[data-error-keys]').forEach(function (el) {
        el.dataset.errorKeys.split(',').forEach(function (raw) {
            const key = raw.trim().toLowerCase();
            if (!key) return;
            const pos = text.indexOf(key);
            if (pos === -1) return;
            if (!best || pos < best.pos || (pos === best.pos && key.length > best.len)) {
                best = {el: el, pos: pos, len: key.length};
            }
        });
    });
    if (best) markFieldError(form, best.el.name || best.el.id);
    return !!best;
}

/* Formulario de sección con su propio botón Guardar.
   opts: {action, submit (botón), multipart (bool), validate(form) → [[campo, msg], ...],
          collect(form) → objeto|FormData (opcional), onSuccess(response)}                */
function bindSectionForm(form, opts) {
    const submit = opts.submit || form.querySelector('[type="submit"]');
    form.addEventListener('input', function (e) {
        if (e.target.type === 'checkbox' && e.target.name) {
            form.querySelectorAll('[name="' + e.target.name + '"].is-invalid').forEach(function (el) { el.classList.remove('is-invalid'); });
        } else if (e.target.classList.contains('is-invalid')) {
            e.target.classList.remove('is-invalid');
            const next = (e.target.closest('.select-wrap') || e.target).nextElementSibling;
            if (next && next.classList.contains('field-error')) next.remove();
        }
    });
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        clearFieldErrors(form);
        const errors = opts.validate ? (opts.validate(form) || []) : [];
        if (errors.length) {
            errors.forEach(function (err) { markFieldError(form, err[0], err[1]); });
            showToast(errors[0][1] || 'Revisa los campos marcados.', 'error');
            const first = form.querySelector('.is-invalid');
            if (first) first.focus();
            return;
        }
        let data = opts.collect ? opts.collect(form) : null;
        if (!data) {
            if (opts.multipart) {
                data = new FormData(form);
            } else {
                data = {};
                new FormData(form).forEach(function (value, key) {
                    if (key in data) data[key] = [].concat(data[key], value);
                    else data[key] = value;
                });
            }
        }
        if (data instanceof FormData) data.set('action', opts.action); else data.action = opts.action;

        setButtonLoading(submit, true, 'Guardando...');
        postAction(data)
            .done(function (response) {
                if (response && response.result === 'ok') {
                    showToast(response.mensaje || 'Cambios guardados correctamente.');
                    if (opts.onSuccess) opts.onSuccess(response);
                } else {
                    const msg = (response && response.mensaje) || 'No se pudieron guardar los cambios.';
                    showToast(msg, 'error');
                    markErrorFromMessage(form, msg);
                }
            })
            .fail(function () { showToast('Error de conexión al guardar los cambios.', 'error'); })
            .always(function () { setButtonLoading(submit, false); });
    });
}

/* ---------- Pestañas de sección (solo móvil) ----------
   Botones [data-section-tab="id"] muestran la .edit-section con ese id. */
function bindSectionTabs() {
    const tabs = document.querySelectorAll('[data-section-tab]');
    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            tabs.forEach(function (t) { t.classList.toggle('is-active', t === tab); });
            document.querySelectorAll('.edit-section').forEach(function (s) {
                s.classList.toggle('is-current', s.id === tab.dataset.sectionTab);
            });
        });
    });
}

/* ---------- Reagendar cita (partial reschedule_modal.html) ----------
   Botones: <button class="js-reschedule" data-id data-doctor-id data-doctor-name data-current
            data-reschedule-action="rescheduleappointment|adminrescheduleappointment"> */
function bindRescheduleButtons() {
    const modal = document.getElementById('rescheduleModal');
    if (!modal) return;
    const submitBtn = document.getElementById('rescheduleSubmit');
    let action = 'rescheduleappointment';
    const picker = SlotPicker.create({
        dateInput: document.getElementById('rescheduleDate'),
        slotsBox: document.getElementById('rescheduleSlots'),
        dateHint: document.getElementById('rescheduleDateHint'),
        onChange: function (state) { submitBtn.disabled = !(state.date && state.time); }
    });

    document.querySelectorAll('.js-reschedule').forEach(function (btn) {
        btn.addEventListener('click', function () {
            action = btn.dataset.rescheduleAction || 'rescheduleappointment';
            document.getElementById('rescheduleId').value = btn.dataset.id;
            document.getElementById('rescheduleDoctor').textContent = btn.dataset.doctorName;
            document.getElementById('rescheduleCurrent').textContent = btn.dataset.current;
            submitBtn.disabled = true;
            picker.load(btn.dataset.doctorId);
            openModal('rescheduleModal');
        });
    });

    document.getElementById('rescheduleForm').addEventListener('submit', function (e) {
        e.preventDefault();
        if (submitBtn.disabled) return;
        setButtonLoading(submitBtn, true, 'Guardando...');
        postAction({
            action: action,
            id: document.getElementById('rescheduleId').value,
            date: picker.state.date,
            time: picker.state.time
        }).done(function (response) {
            if (response && response.result === 'ok') {
                reloadWithInfo(response.mensaje || 'Cita reagendada correctamente.');
            } else {
                showToast((response && response.mensaje) || 'No se pudo reagendar la cita.', 'error');
                setButtonLoading(submitBtn, false);
                picker.reloadSlots();
            }
        }).fail(function () {
            showToast('Error de conexión al reagendar la cita.', 'error');
            setButtonLoading(submitBtn, false);
        });
    });
}

/* ---------- Especialidad → médico → tarjeta → fecha y turnos ----------
   Compartido por Reservar Cita (paciente) y Agendar cita (administrativo).
   Usa los ids del partial doctor_preview_card.html (emptyStateCard, loadingCard, doctorCard, doc*).
   opts: {specSelect, docSelect, docHint, dateInput, slotsBox, dateHint, noPhoto, onChange()}
   Devuelve {ready(), values(), reset(), preset(specId, doctorId), reloadSlots()}. */
const DoctorPicker = (function () {
    function create(opts) {
        const specSelect = opts.specSelect;
        const docSelect = opts.docSelect;
        let currentDoctor = null;
        let specReq = 0, doctorReq = 0;

        function notify() { if (opts.onChange) opts.onChange(); }

        const picker = SlotPicker.create({
            dateInput: opts.dateInput,
            slotsBox: opts.slotsBox,
            dateHint: opts.dateHint,
            onChange: notify
        });

        function showCard(which) {
            document.getElementById('emptyStateCard').hidden = which !== 'empty';
            document.getElementById('loadingCard').hidden = which !== 'loading';
            document.getElementById('doctorCard').hidden = which !== 'doctor';
        }

        function showEmptyState() {
            doctorReq++;
            currentDoctor = null;
            showCard('empty');
            picker.reset();
        }

        function renderDoctorCard(doc) {
            currentDoctor = doc;
            const photo = document.getElementById('docPhoto');
            photo.onerror = function () { this.onerror = null; this.src = opts.noPhoto; };
            photo.src = doc.photo_doctor || opts.noPhoto;
            photo.alt = doc.name_doctor || 'Médico';
            const has = function (v) { return v !== null && v !== undefined && v !== ''; };
            const years = doc.years_experience;
            document.getElementById('docName').textContent = doc.name_doctor || '--';
            document.getElementById('docSpecialty').textContent = doc.specialities_doctor || '--';
            document.querySelector('#docLocation [data-field]').textContent = doc.country_doctor || 'No disponible';
            document.getElementById('docExp').textContent = has(years) ? years + (Number(years) === 1 ? ' Año' : ' Años') : '--';
            document.getElementById('docPatients').textContent = has(doc.patients_count) ? doc.patients_count : '--';
            document.getElementById('docRoom').textContent = doc.office || 'Por asignar';
            document.getElementById('docPrice').textContent = has(doc.price) ? '$' + doc.price + ' USD' : '--';
            document.getElementById('docBio').textContent = doc.bio || 'Sin descripción disponible.';
            showCard('doctor');
        }

        function onSpecialtyChange(presetDoctorId) {
            const token = ++specReq;
            docSelect.innerHTML = '<option value="">-- Seleccionar Médico --</option>';
            docSelect.disabled = true;
            showEmptyState();
            notify();

            if (!specSelect.value) {
                docSelect.options[0].textContent = '-- Primero elija especialidad --';
                setHint(opts.docHint, 'Selecciona una especialidad para desplegar médicos.');
                return;
            }
            docSelect.options[0].textContent = 'Cargando médicos...';
            setHint(opts.docHint, '');
            $.getJSON('/panel', {action: 'searchdoctorbyspeciality', id_speciality: specSelect.value})
                .done(function (response) {
                    if (token !== specReq) return;
                    const results = (response && response.results) || [];
                    docSelect.options[0].textContent = '-- Seleccionar Médico --';
                    if (!results.length) {
                        setHint(opts.docHint, 'No hay médicos disponibles para esta especialidad.');
                        return;
                    }
                    results.forEach(function (item) { docSelect.appendChild(new Option(item.text, item.id)); });
                    docSelect.disabled = false;
                    if (presetDoctorId && results.some(function (r) { return String(r.id) === String(presetDoctorId); })) {
                        docSelect.value = String(presetDoctorId);
                        onDoctorChange();
                    }
                })
                .fail(function () {
                    if (token !== specReq) return;
                    docSelect.options[0].textContent = '-- Seleccionar Médico --';
                    setHint(opts.docHint, 'No se pudieron cargar los médicos.');
                    showToast('No se pudieron cargar los médicos. Intenta nuevamente.', 'error');
                });
        }

        function onDoctorChange() {
            const doctorId = docSelect.value;
            if (!doctorId) { showEmptyState(); notify(); return; }
            const token = ++doctorReq;
            currentDoctor = null;
            picker.reset('Cargando fechas...');
            showCard('loading');
            $.getJSON('/panel', {action: 'getdoctorinfo', id_doctor: doctorId})
                .done(function (response) {
                    if (token !== doctorReq) return;
                    if (!response || response.display === false || !response.data || Array.isArray(response.data)) {
                        showEmptyState();
                        showToast((response && response.message) || 'No se pudo obtener la información del médico.', 'error');
                        return;
                    }
                    renderDoctorCard(response.data);
                    picker.load(doctorId);
                })
                .fail(function () {
                    if (token !== doctorReq) return;
                    showEmptyState();
                    showToast('No se pudo obtener la información del médico.', 'error');
                });
        }

        specSelect.addEventListener('change', function () { onSpecialtyChange(); });
        docSelect.addEventListener('change', onDoctorChange);

        return {
            ready: function () {
                return !!(specSelect.value && docSelect.value && currentDoctor && picker.state.date && picker.state.time);
            },
            values: function () {
                return {speciality: specSelect.value, doctor: docSelect.value, date: picker.state.date, time: picker.state.time};
            },
            reset: function () { specSelect.value = ''; onSpecialtyChange(); },
            preset: function (specId, doctorId) {
                if (specId && specSelect.querySelector('option[value="' + CSS.escape(String(specId)) + '"]')) {
                    specSelect.value = String(specId);
                }
                if (specSelect.value) onSpecialtyChange(doctorId);
            },
            reloadSlots: function () { picker.reloadSlots(); }
        };
    }
    return {create: create};
})();

/* ---------- Buscador de pacientes con autocompletado ----------
   PatientSearch.create({input, list, hidden, selectedBox, selectedText, changeBtn, preset, onChange})
   GET searchpatients&q= (mín. 2 caracteres) → {results:[{id, text, document, hc}]}, debounce 300 ms. */
const PatientSearch = (function () {
    function create(opts) {
        let timer = null, req = 0, items = [], active = -1;

        function close() { opts.list.hidden = true; active = -1; }

        function select(item) {
            opts.hidden.value = item ? item.id : '';
            if (item) {
                const extra = [item.document ? 'C.I. ' + item.document : '', item.hc || ''].filter(Boolean).join(' · ');
                opts.selectedText.innerHTML = '<span class="font-bold text-slate-900">' + escapeHtml(item.text) + '</span>' +
                    (extra ? '<br><span class="text-xs text-slate-500">' + escapeHtml(extra) + '</span>' : '');
            }
            opts.selectedBox.hidden = !item;
            opts.input.closest('.autocomplete').hidden = !!item;
            close();
            if (opts.onChange) opts.onChange(item);
        }

        function render() {
            if (!items.length) {
                opts.list.innerHTML = '<div class="autocomplete-empty">No se encontraron pacientes.</div>';
            } else {
                opts.list.innerHTML = items.map(function (it, i) {
                    const extra = [it.document ? 'C.I. ' + it.document : '', it.hc || ''].filter(Boolean).join(' · ');
                    return '<button type="button" class="autocomplete-item' + (i === active ? ' is-active' : '') + '" data-index="' + i + '">' +
                        '<span>' + escapeHtml(it.text) + '</span>' + (extra ? '<small>' + escapeHtml(extra) + '</small>' : '') + '</button>';
                }).join('');
            }
            opts.list.hidden = false;
        }

        function search(q) {
            const token = ++req;
            $.getJSON('/panel', {action: 'searchpatients', q: q})
                .done(function (response) {
                    if (token !== req) return;
                    items = (response && response.results) || [];
                    active = -1;
                    render();
                })
                .fail(function () { if (token === req) showToast('No se pudo buscar pacientes.', 'error'); });
        }

        opts.input.addEventListener('input', function () {
            clearTimeout(timer);
            const q = opts.input.value.trim();
            if (q.length < 2) { req++; close(); return; }
            timer = setTimeout(function () { search(q); }, 300);
        });
        opts.input.addEventListener('keydown', function (e) {
            if (opts.list.hidden || !items.length) return;
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                active = (active + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
                render();
            } else if (e.key === 'Enter' && active >= 0) {
                e.preventDefault();
                select(items[active]);
            } else if (e.key === 'Escape') {
                close();
            }
        });
        opts.list.addEventListener('mousedown', function (e) {
            const btn = e.target.closest('[data-index]');
            if (btn) { e.preventDefault(); select(items[Number(btn.dataset.index)]); }
        });
        opts.input.addEventListener('blur', function () { setTimeout(close, 150); });
        if (opts.changeBtn) {
            opts.changeBtn.addEventListener('click', function () {
                select(null);
                opts.input.value = '';
                opts.input.focus();
            });
        }
        if (opts.preset && opts.preset.id) select(opts.preset);

        return {value: function () { return opts.hidden.value; }, clear: function () { select(null); opts.input.value = ''; }};
    }
    return {create: create};
})();

/* ---------- Datos personales compartidos (perfil del paciente y administración) ---------- */
// Flatpickr de fecha de nacimiento (máx. hoy) con la edad en vivo en `output`
function initBirthdateField(input, output) {
    function updateAge() {
        const age = calcAge(input.value);
        output.classList.toggle('is-muted', age === null);
        output.innerHTML = age === null ? '' : '<i class="fa-solid fa-cake-candles"></i> ' + age + (age === 1 ? ' año' : ' años');
    }
    flatpickr(input, {
        locale: (flatpickr.l10ns && flatpickr.l10ns.es) ? 'es' : 'default',
        dateFormat: 'Y-m-d',
        altInput: true,
        altFormat: 'd/m/Y',
        altInputClass: input.className,
        maxDate: 'today',
        disableMobile: true,
        onChange: updateAge
    });
    updateAge();
}

// Errores [[campo, msg]] de los campos personales (partial person_personal_fields.html)
function validatePersonalFields(form) {
    const errors = [];
    const val = function (n) { return form.elements[n] ? String(form.elements[n].value || '').trim() : ''; };
    if (!val('names')) errors.push(['names', 'Los nombres son obligatorios.']);
    if (!val('lastnames')) errors.push(['lastnames', 'Los apellidos son obligatorios.']);
    const type = form.elements.typedocument;
    const isCedula = type && type.selectedOptions[0] && type.selectedOptions[0].dataset.cedula === '1';
    const doc = val('document');
    if (!doc) errors.push(['document', 'El documento es obligatorio.']);
    else if (isCedula && !/^\d{10}$/.test(doc)) errors.push(['document', 'La cédula debe tener 10 dígitos.']);
    const birth = val('birthdate');
    if (!birth) errors.push(['birthdate', 'La fecha de nacimiento es obligatoria.']);
    else if (calcAge(birth) === null) errors.push(['birthdate', 'La fecha de nacimiento no puede ser futura.']);
    const photo = form.elements.photo && form.elements.photo.files && form.elements.photo.files[0];
    const photoError = validatePhoto(photo);
    if (photoError) errors.push(['photo', photoError]);
    return errors;
}

// Errores de correo (obligatorio) y correo institucional (opcional)
function validateContactFields(form) {
    const errors = [];
    const email = form.elements.email ? form.elements.email.value.trim() : '';
    if (!email) errors.push(['email', 'El correo electrónico es obligatorio.']);
    else if (!isValidEmail(email)) errors.push(['email', 'El correo electrónico no tiene un formato válido.']);
    const inst = form.elements.emailinst ? form.elements.emailinst.value.trim() : '';
    if (inst && !isValidEmail(inst)) errors.push(['emailinst', 'El correo institucional no tiene un formato válido.']);
    return errors;
}

// Cascada estándar de ubicación con los ids country/province/canton/parish
function bindLocationCascade(root) {
    const byId = function (id) { return (root || document).querySelector('#' + id); };
    bindCascadeSelects([
        {select: byId('country')},
        {select: byId('province'), action: 'getprovinces', param: 'country_id', placeholder: '-- Provincia --'},
        {select: byId('canton'), action: 'getcantons', param: 'province_id', placeholder: '-- Cantón --'},
        {select: byId('parish'), action: 'getparishes', param: 'canton_id', placeholder: '-- Parroquia --'}
    ]);
}

/* ---------- Modal de credenciales (partial credentials_modal.html) ----------
   CredentialsModal.show({username, password}, {title, doneUrl}) */
const CredentialsModal = (function () {
    function copy(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text).then(function () { showToast('Copiado al portapapeles.'); });
        }
        // Respaldo para contextos no seguros (http)
        const area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', '');
        area.className = 'sr-only';
        document.body.appendChild(area);
        area.select();
        let ok = false;
        try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
        area.remove();
        showToast(ok ? 'Copiado al portapapeles.' : 'No se pudo copiar; selecciónalo manualmente.', ok ? undefined : 'error');
        return Promise.resolve();
    }

    let bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        document.querySelectorAll('#credentialsModal [data-copy-target]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                copy(document.getElementById(btn.dataset.copyTarget).textContent);
            });
        });
        document.getElementById('credCopyAll').addEventListener('click', function () {
            copy('Usuario: ' + document.getElementById('credUsername').textContent +
                 '\nContraseña temporal: ' + document.getElementById('credPassword').textContent);
        });
        document.getElementById('credPrint').addEventListener('click', function () { window.print(); });
    }

    function show(credentials, opts) {
        opts = opts || {};
        bind();
        document.getElementById('credentialsTitle').textContent = opts.title || 'Acceso generado';
        document.getElementById('credUsername').textContent = credentials.username || '--';
        document.getElementById('credPassword').textContent = credentials.password || '--';
        if (opts.doneUrl) document.getElementById('credDone').href = opts.doneUrl;
        document.body.classList.add('is-printing-modal');
        openModal('credentialsModal');
    }

    return {show: show};
})();

/* ---------- Resaltar un elemento de lista (?highlight=<id>) ----------
   Elementos con data-highlight-id; se desplaza hasta el que coincide. */
function highlightListItem(id) {
    if (!id) return;
    const el = document.querySelector('[data-highlight-id="' + CSS.escape(String(id)) + '"]');
    if (!el) return;
    el.classList.add('is-highlighted');
    el.scrollIntoView({behavior: 'smooth', block: 'center'});
    const url = new URL(window.location.href);
    url.searchParams.delete('highlight');
    window.history.replaceState(null, '', url.toString());
}
