/* =====================================================
   CHOCOLATES BYB - JAVASCRIPT PRINCIPAL
   ===================================================== */

// Esperar a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function() {
    
    // Inicializar todos los componentes
    initializeNavigation();
    initializeSmoothScroll();
    initializeFormValidation();
    initializeAnimations();
    initializeLazyLoading();
    initializeTooltips();
    
    // Si estamos en la página del catálogo, inicializar funciones específicas
    if (document.getElementById('orderForm')) {
        initializeCatalog();
    }
    
    // Si estamos en el panel admin, inicializar funciones administrativas
    if (document.querySelector('.admin-content')) {
        initializeAdminFunctions();
    }
});

/* =====================================================
   NAVEGACIÓN
   ===================================================== */

function initializeNavigation() {
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.querySelector('.nav-menu');
    
    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function() {
            navMenu.classList.toggle('active');
            
            // Cambiar icono del botón
            const icon = this.querySelector('i');
            if (navMenu.classList.contains('active')) {
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-times');
            } else {
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        });
        
        // Cerrar menú al hacer clic en un enlace (móvil)
        const navLinks = document.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                navMenu.classList.remove('active');
                const icon = navToggle.querySelector('i');
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            });
        });
        
        // Cerrar menú al hacer clic fuera
        document.addEventListener('click', function(event) {
            if (!event.target.closest('.navbar')) {
                navMenu.classList.remove('active');
                const icon = navToggle.querySelector('i');
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        });
    }
}

/* =====================================================
   SMOOTH SCROLL
   ===================================================== */

function initializeSmoothScroll() {
    // Manejar todos los enlaces que empiezan con #
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                const headerOffset = 80; // Altura del header fijo
                const elementPosition = targetElement.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                
                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

/* =====================================================
   VALIDACIÓN DE FORMULARIOS
   ===================================================== */

function initializeFormValidation() {
    // Validación en tiempo real para campos requeridos
    const requiredInputs = document.querySelectorAll('[required]');
    
    requiredInputs.forEach(input => {
        // Validar al perder el foco
        input.addEventListener('blur', function() {
            validateField(this);
        });
        
        // Limpiar error al escribir
        input.addEventListener('input', function() {
            if (this.classList.contains('error')) {
                clearFieldError(this);
            }
        });
    });
    
    // Validación de teléfono cubano
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(input => {
        input.addEventListener('blur', function() {
            validateCubanPhone(this);
        });
    });
}

function validateField(field) {
    const value = field.value.trim();
    
    if (value === '') {
        showFieldError(field, 'Este campo es obligatorio');
        return false;
    }
    
    // Validaciones específicas por tipo
    if (field.type === 'email') {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            showFieldError(field, 'Por favor ingresa un email válido');
            return false;
        }
    }
    
    clearFieldError(field);
    return true;
}

function validateCubanPhone(field) {
    const value = field.value.trim();
    if (value === '') return true; // Solo validar si hay valor
    
    // Formato esperado: +53 5XXXXXXX o 5XXXXXXX
    const phoneRegex = /^(\+53\s?)?5\d{7}$/;
    
    if (!phoneRegex.test(value.replace(/\s/g, ''))) {
        showFieldError(field, 'Formato: +53 5XXXXXXX');
        return false;
    }
    
    clearFieldError(field);
    return true;
}

function showFieldError(field, message) {
    field.classList.add('error');
    
    // Remover mensaje de error anterior si existe
    const existingError = field.parentElement.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }
    
    // Crear y mostrar nuevo mensaje de error
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    field.parentElement.appendChild(errorDiv);
}

function clearFieldError(field) {
    field.classList.remove('error');
    const errorMessage = field.parentElement.querySelector('.error-message');
    if (errorMessage) {
        errorMessage.remove();
    }
}

/* =====================================================
   ANIMACIONES
   ===================================================== */

function initializeAnimations() {
    // Configurar Intersection Observer para animaciones al scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                
                // Si el elemento tiene animación de contador
                if (entry.target.hasAttribute('data-count')) {
                    animateCounter(entry.target);
                }
                
                // Dejar de observar después de animar
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observar elementos con clase animate-on-scroll
    const animatedElements = document.querySelectorAll('.animate-on-scroll');
    animatedElements.forEach(el => {
        observer.observe(el);
    });
    
    // Observar cards para animación de entrada
    const cards = document.querySelectorAll('.feature-card, .product-preview-card, .testimonial-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transitionDelay = `${index * 0.1}s`;
        observer.observe(card);
    });
}

function animateCounter(element) {
    const target = parseInt(element.getAttribute('data-count'));
    const duration = 2000; // 2 segundos
    const step = target / (duration / 16); // 60 FPS
    let current = 0;
    
    const timer = setInterval(() => {
        current += step;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        element.textContent = Math.floor(current).toLocaleString();
    }, 16);
}

/* =====================================================
   LAZY LOADING DE IMÁGENES
   ===================================================== */

function initializeLazyLoading() {
    const lazyImages = document.querySelectorAll('img[data-src]');
    
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver(function(entries) {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.add('loaded');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        lazyImages.forEach(img => imageObserver.observe(img));
    } else {
        // Fallback para navegadores antiguos
        lazyImages.forEach(img => {
            img.src = img.dataset.src;
            img.classList.add('loaded');
        });
    }
}

/* =====================================================
   TOOLTIPS
   ===================================================== */

function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    
    tooltipElements.forEach(element => {
        let tooltip = null;
        
        element.addEventListener('mouseenter', function(e) {
            const text = this.getAttribute('data-tooltip');
            tooltip = createTooltip(text);
            positionTooltip(tooltip, this);
            document.body.appendChild(tooltip);
            
            // Animación de entrada
            setTimeout(() => {
                tooltip.classList.add('show');
            }, 10);
        });
        
        element.addEventListener('mouseleave', function() {
            if (tooltip) {
                tooltip.classList.remove('show');
                setTimeout(() => {
                    tooltip.remove();
                }, 300);
            }
        });
    });
}

function createTooltip(text) {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = text;
    return tooltip;
}

function positionTooltip(tooltip, element) {
    const rect = element.getBoundingClientRect();
    const tooltipHeight = 35; // Altura aproximada del tooltip
    
    tooltip.style.position = 'absolute';
    tooltip.style.left = rect.left + (rect.width / 2) + 'px';
    tooltip.style.top = (rect.top - tooltipHeight - 10) + window.pageYOffset + 'px';
}

/* =====================================================
   FUNCIONES DEL CATÁLOGO
   ===================================================== */

function initializeCatalog() {
    // Todas las funciones relacionadas con el catálogo están definidas
    // directamente en catalogo.html para mejor organización
    console.log('Catálogo inicializado');
}

/* =====================================================
   FUNCIONES ADMINISTRATIVAS
   ===================================================== */

function initializeAdminFunctions() {
    // Función para mostrar notificaciones toast
    window.showNotification = function(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        
        const icon = {
            'success': 'check-circle',
            'error': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        }[type] || 'info-circle';
        
        notification.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        document.body.appendChild(notification);
        
        // Animación de entrada
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Auto-cerrar después de 5 segundos
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 5000);
    };
    
    // Confirmación antes de acciones destructivas
    window.confirmAction = function(message, callback) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'block';
        
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Confirmar acción</h3>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                    <div class="modal-buttons">
                        <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">
                            Cancelar
                        </button>
                        <button class="btn btn-danger" id="confirmButton">
                            Confirmar
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        document.getElementById('confirmButton').addEventListener('click', function() {
            callback();
            modal.remove();
        });
        
        // Cerrar al hacer clic fuera
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.remove();
            }
        });
    };
}

/* =====================================================
   UTILIDADES
   ===================================================== */

// Formatear números con separadores de miles
function formatNumber(number) {
    return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Formatear fecha en formato cubano
function formatDate(date) {
    const options = { 
        day: 'numeric', 
        month: 'long', 
        year: 'numeric' 
    };
    return new Date(date).toLocaleDateString('es-CU', options);
}

// Debounce para optimizar eventos frecuentes
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle para limitar la frecuencia de ejecución
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/* =====================================================
   LOCAL STORAGE
   ===================================================== */

// Guardar en localStorage con prefijo para evitar conflictos
function saveToStorage(key, value) {
    const prefixedKey = 'chocolatesbyb_' + key;
    try {
        localStorage.setItem(prefixedKey, JSON.stringify(value));
        return true;
    } catch (e) {
        console.error('Error al guardar en localStorage:', e);
        return false;
    }
}

// Recuperar de localStorage
function getFromStorage(key) {
    const prefixedKey = 'chocolatesbyb_' + key;
    try {
        const item = localStorage.getItem(prefixedKey);
        return item ? JSON.parse(item) : null;
    } catch (e) {
        console.error('Error al leer de localStorage:', e);
        return null;
    }
}

// Limpiar datos antiguos de localStorage (más de 30 días)
function cleanOldStorage() {
    const thirtyDaysAgo = Date.now() - (30 * 24 * 60 * 60 * 1000);
    
    Object.keys(localStorage).forEach(key => {
        if (key.startsWith('chocolatesbyb_')) {
            try {
                const item = JSON.parse(localStorage.getItem(key));
                if (item.timestamp && item.timestamp < thirtyDaysAgo) {
                    localStorage.removeItem(key);
                }
            } catch (e) {
                // Si no se puede parsear, probablemente es datos corruptos
                localStorage.removeItem(key);
            }
        }
    });
}

// Ejecutar limpieza al cargar
cleanOldStorage();

/* =====================================================
   MANEJO DE ERRORES GLOBAL
   ===================================================== */

window.addEventListener('error', function(event) {
    console.error('Error global:', event.error);
    
    // En producción, podrías enviar estos errores a un servicio de logging
    if (window.location.hostname !== 'localhost') {
        // Enviar error a servicio de logging
        // logErrorToService(event.error);
    }
});

// Manejar promesas rechazadas
window.addEventListener('unhandledrejection', function(event) {
    console.error('Promesa rechazada:', event.reason);
    event.preventDefault();
});

/* =====================================================
   OPTIMIZACIÓN DE RENDIMIENTO
   ===================================================== */

// Retrasar ejecución de scripts no críticos
if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
        // Inicializar funciones no críticas
        initializeLazyLoading();
        cleanOldStorage();
    });
} else {
    // Fallback para navegadores antiguos
    setTimeout(() => {
        initializeLazyLoading();
        cleanOldStorage();
    }, 1);
}

// Service Worker para PWA (si decides implementarlo en el futuro)
if ('serviceWorker' in navigator && window.location.hostname !== 'localhost') {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => console.log('ServiceWorker registrado'))
            .catch(err => console.log('ServiceWorker falló:', err));
    });
}

/* =====================================================
   EXPORTAR FUNCIONES PARA USO GLOBAL
   ===================================================== */

window.ChocolatesByB = {
    formatNumber,
    formatDate,
    saveToStorage,
    getFromStorage,
    showNotification: window.showNotification,
    confirmAction: window.confirmAction
};
