// ==================== Global Variables ====================
let currentJobId = null;
let currentFile = null;
let monitorInterval = null;
let startTime = null;

// ==================== Initialize ====================
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    console.log('🎬 Comfy_Img_to_Loop initialized');
    
    // Setup drag & drop
    setupDragAndDrop();
    
    // Setup sliders
    setupSliders();
    
    // Load gallery
    loadGallery();
    
    // Refresh gallery every 10s
    setInterval(loadGallery, 10000);
}

// ==================== Drag & Drop ====================
function setupDragAndDrop() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    
    // Drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    // Highlight drop zone
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        });
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        });
    });
    
    // Handle drop
    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });
    
    // Handle file input
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
    
    // Click on drop zone
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });
}

function handleFile(file) {
    // Validate file
    if (!file.type.startsWith('image/')) {
        showAlert('Erreur', 'Veuillez sélectionner une image', 'danger');
        return;
    }
    
    if (file.size > 100 * 1024 * 1024) {
        showAlert('Erreur', 'Fichier trop volumineux (max 100MB)', 'danger');
        return;
    }
    
    currentFile = file;
    
    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('previewImg').src = e.target.result;
        document.querySelector('.preview-filename').textContent = file.name;
        document.getElementById('dropZone').style.display = 'none';
        document.getElementById('imagePreview').style.display = 'block';
    };
    reader.readAsDataURL(file);
    
    console.log('✅ Image loaded:', file.name);
}

function clearImage() {
    currentFile = null;
    document.getElementById('dropZone').style.display = 'flex';
    document.getElementById('imagePreview').style.display = 'none';
    document.getElementById('fileInput').value = '';
}

// ==================== Sliders ====================
function setupSliders() {
    // Steps slider
    const stepsInput = document.getElementById('stepsInput');
    const stepsValue = document.getElementById('stepsValue');
    stepsInput.addEventListener('input', (e) => {
        stepsValue.textContent = e.target.value;
    });
    
    // CFG Scale slider
    const cfgInput = document.getElementById('cfgInput');
    const cfgValue = document.getElementById('cfgValue');
    cfgInput.addEventListener('input', (e) => {
        cfgValue.textContent = e.target.value;
    });
    
    // Frames slider
    const framesInput = document.getElementById('framesInput');
    const framesValue = document.getElementById('framesValue');
    framesInput.addEventListener('input', (e) => {
        framesValue.textContent = e.target.value;
    });
    
    // FPS slider
    const fpsInput = document.getElementById('fpsInput');
    const fpsValue = document.getElementById('fpsValue');
    fpsInput.addEventListener('input', (e) => {
        fpsValue.textContent = e.target.value;
    });
}

// ==================== Generation ====================
async function startGeneration() {
    // Validate
    if (!currentFile) {
        showAlert('Attention', 'Veuillez sélectionner une image', 'warning');
        return;
    }
    
    // Get parameters
    const formData = new FormData();
    formData.append('image', currentFile);
    formData.append('prompt', document.getElementById('promptInput').value);
    
    const parameters = {
        steps: parseInt(document.getElementById('stepsInput').value),
        cfg_scale: parseFloat(document.getElementById('cfgInput').value),
        frames: parseInt(document.getElementById('framesInput').value),
        fps: parseInt(document.getElementById('fpsInput').value),
        noise_level: document.querySelector('input[name="noiseLevel"]:checked').value
    };
    
    formData.append('parameters', JSON.stringify(parameters));
    
    // Update UI
    document.getElementById('generateBtn').disabled = true;
    document.getElementById('generateBtn').innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Génération...';
    
    try {
        // Send request
        const response = await fetch('/api/generate', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentJobId = data.job_id;
            
            // Show monitoring section
            document.getElementById('currentJob').style.display = 'block';
            document.getElementById('resultSection').style.display = 'none';
            
            // Update stats
            document.getElementById('jobFrames').textContent = parameters.frames;
            document.getElementById('jobSteps').textContent = parameters.steps;
            
            // Start monitoring
            startTime = Date.now();
            startMonitoring();
            
            // Scroll to monitor
            document.getElementById('monitor').scrollIntoView({ behavior: 'smooth' });
            
            showAlert('Succès', 'Génération lancée!', 'success');
        } else {
            throw new Error(data.error || 'Erreur lors de la génération');
        }
        
    } catch (error) {
        console.error('Error:', error);
        showAlert('Erreur', error.message, 'danger');
        document.getElementById('generateBtn').disabled = false;
        document.getElementById('generateBtn').innerHTML = '<i class="bi bi-stars"></i> Générer le Cinemagraph';
    }
}

// ==================== Monitoring ====================
function startMonitoring() {
    if (monitorInterval) {
        clearInterval(monitorInterval);
    }
    
    monitorInterval = setInterval(updateJobStatus, 2000);
    updateJobStatus(); // First call immediately
}

async function updateJobStatus() {
    if (!currentJobId) return;
    
    try {
        const response = await fetch(`/api/jobs/${currentJobId}`);
        const job = await response.json();
        
        // Update progress
        const progress = Math.round(job.progress * 100);
        document.getElementById('progressBar').style.width = `${progress}%`;
        document.getElementById('progressText').textContent = `${progress}%`;
        
        // Update status
        document.getElementById('currentJobStatus').textContent = getStatusText(job.status);
        document.getElementById('currentStep').textContent = job.current_step || '-';
        
        // Update elapsed time
        if (startTime) {
            const elapsed = Math.round((Date.now() - startTime) / 1000);
            document.getElementById('elapsedTime').textContent = `${elapsed}s`;
        }
        
        // Check if completed
        if (job.status === 'completed') {
            clearInterval(monitorInterval);
            showResult(job);
            loadGallery();
        } else if (job.status === 'failed') {
            clearInterval(monitorInterval);
            showAlert('Erreur', job.error_message || 'Génération échouée', 'danger');
            resetUI();
        }
        
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

function getStatusText(status) {
    const statusMap = {
        'pending': 'En attente...',
        'uploading': 'Upload de l\'image...',
        'processing': 'Génération en cours...',
        'uploading_result': 'Upload sur OwnCloud...',
        'completed': 'Terminé!',
        'failed': 'Échec',
        'cancelled': 'Annulé'
    };
    return statusMap[status] || status;
}

function showResult(job) {
    // Hide current job
    document.getElementById('currentJob').style.display = 'none';
    
    // Show result
    document.getElementById('resultSection').style.display = 'block';
    
    // Set download link
    const downloadLink = document.getElementById('downloadLink');
    downloadLink.href = `/api/jobs/${job.job_id}/download`;
    
    // Set OwnCloud link if available
    if (job.owncloud_link) {
        const owncloudLink = document.getElementById('owncloudLink');
        owncloudLink.href = job.owncloud_link;
        owncloudLink.style.display = 'inline-block';
    }
    
    // Reset button
    resetUI();
    
    // Clear image
    clearImage();
}

function resetUI() {
    document.getElementById('generateBtn').disabled = false;
    document.getElementById('generateBtn').innerHTML = '<i class="bi bi-stars"></i> Générer le Cinemagraph';
    currentJobId = null;
    startTime = null;
}

function cancelJob() {
    if (monitorInterval) {
        clearInterval(monitorInterval);
    }
    document.getElementById('currentJob').style.display = 'none';
    resetUI();
    showAlert('Info', 'Job annulé', 'info');
}

// ==================== Gallery ====================
async function loadGallery() {
    try {
        const response = await fetch('/api/jobs?limit=20');
        const data = await response.json();
        
        const galleryGrid = document.getElementById('galleryGrid');
        const emptyGallery = document.getElementById('emptyGallery');
        
        if (data.jobs && data.jobs.length > 0) {
            emptyGallery.style.display = 'none';
            galleryGrid.style.display = 'flex';
            
            galleryGrid.innerHTML = data.jobs.map(job => createGalleryItem(job)).join('');
        } else {
            galleryGrid.style.display = 'none';
            emptyGallery.style.display = 'block';
        }
        
    } catch (error) {
        console.error('Error loading gallery:', error);
    }
}

function createGalleryItem(job) {
    const statusColors = {
        'completed': 'success',
        'failed': 'danger',
        'processing': 'primary',
        'pending': 'warning'
    };
    
    const color = statusColors[job.status] || 'secondary';
    const date = new Date(job.created_at).toLocaleString('fr-FR');
    
    return `
        <div class="col gallery-item">
            <div class="card h-100">
                <div class="position-relative">
                    <span class="badge bg-${color} gallery-badge">${getStatusText(job.status)}</span>
                    ${job.status === 'completed' ? 
                        `<img src="/api/jobs/${job.job_id}/thumbnail" class="card-img-top" alt="Cinemagraph" onerror="this.src='https://via.placeholder.com/400x200?text=Cinemagraph'">` :
                        `<div class="bg-secondary" style="height: 200px; display: flex; align-items: center; justify-content: center;">
                            <i class="bi bi-hourglass-split text-white fs-1"></i>
                        </div>`
                    }
                </div>
                <div class="card-body">
                    <h6 class="card-title text-truncate">
                        <i class="bi bi-film"></i> ${job.job_id.substring(0, 8)}
                    </h6>
                    <p class="card-text small text-muted mb-2">
                        <i class="bi bi-clock"></i> ${date}
                    </p>
                    ${job.prompt ? `<p class="card-text small text-truncate">"${job.prompt}"</p>` : ''}
                    ${job.status === 'completed' ? `
                        <div class="d-grid gap-2">
                            <a href="/api/jobs/${job.job_id}/download" class="btn btn-sm btn-primary">
                                <i class="bi bi-download"></i> Télécharger
                            </a>
                            ${job.owncloud_link ? `
                                <a href="${job.owncloud_link}" target="_blank" class="btn btn-sm btn-outline-info">
                                    <i class="bi bi-cloud"></i> OwnCloud
                                </a>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

// ==================== Alerts ====================
function showAlert(title, message, type = 'info') {
    // Create alert (could use toast notifications for better UX)
    console.log(`${type.toUpperCase()}: ${title} - ${message}`);
    
    // You could implement Bootstrap toasts here for better UX
}

// ==================== Utility ====================
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
}
