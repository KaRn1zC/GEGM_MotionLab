.PHONY: help build up down restart logs shell test clean

# Variables
DOCKER_COMPOSE = docker-compose
IMAGE_NAME = comfy_img_to_loop
CONTAINER_NAME = comfy_img_to_loop

help: ## Afficher cette aide
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-35s\033[0m %s\n", $$1, $$2}'

build: ## Construire l'image Docker
	@echo "🔨 Building Docker image..."
	$(DOCKER_COMPOSE) build

up: ## Démarrer les services
	@echo "🚀 Starting services..."
	$(DOCKER_COMPOSE) up -d

down: ## Arrêter les services
	@echo "🛑 Stopping services..."
	$(DOCKER_COMPOSE) down

restart: down up ## Redémarrer les services

logs: ## Voir les logs
	$(DOCKER_COMPOSE) logs -f

logs-app: ## Voir les logs de l'application uniquement
	$(DOCKER_COMPOSE) logs -f comfy_img_to_loop

shell: ## Ouvrir un shell dans le conteneur
	$(DOCKER_COMPOSE) exec comfy_img_to_loop /bin/bash

test: ## Exécuter les tests dans le conteneur
	$(DOCKER_COMPOSE) exec comfy_img_to_loop pytest tests/ -v

test-workflows: ## Tester les workflows
	$(DOCKER_COMPOSE) exec comfy_img_to_loop python scripts/test_workflows.py

health: ## Vérifier le health status
	@echo "🏥 Health check..."
	@curl -s http://localhost:5000/health | python -m json.tool

clean: ## Nettoyer les conteneurs et volumes
	@echo "🧹 Cleaning up..."
	$(DOCKER_COMPOSE) down -v
	docker system prune -f

rebuild: clean build up ## Rebuild complet

dev: ## Démarrer en mode développement
	@echo "🔧 Starting in development mode..."
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.override.yml up

prod: ## Démarrer en mode production
	@echo "🚀 Starting in production mode..."
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d

ps: ## Voir les conteneurs en cours
	$(DOCKER_COMPOSE) ps

stats: ## Voir les stats des conteneurs
	docker stats $(CONTAINER_NAME)

# Alias pratiques
start: up
stop: down
status: ps

# ==================== Model Management ====================

download-models: ## Télécharger un modèle localement: make download-models MODEL=<nom>
	@if [ -z "$(MODEL)" ]; then \
		echo "Usage: make download-models MODEL=<model_name>"; \
		echo ""; echo "Modèles disponibles:"; \
		python -m src.model_registry list-models 2>/dev/null || echo "  (registre indisponible)"; exit 1; fi
	@echo "📥 Téléchargement du modèle $(MODEL)..."
	./scripts/setup_wan22_native.sh $(MODEL)

test-download-models: ## Tester le téléchargement depuis OwnCloud: make test-download-models MODEL=<nom>
	@if [ -z "$(MODEL)" ]; then echo "Usage: make test-download-models MODEL=<model_name>"; exit 1; fi
	@echo "🧪 Test téléchargement OwnCloud..."
	python scripts/download_models_from_owncloud.py --model $(MODEL) --target-dir ./test_models
	@echo "✅ Test terminé - vérifiez ./test_models/"

models-clean: ## Supprimer les modèles locaux d'un modèle: make models-clean MODEL=<nom>
	@if [ -z "$(MODEL)" ]; then echo "Usage: make models-clean MODEL=<model_name>"; exit 1; fi
	@echo "🗑️  Nettoyage du modèle $(MODEL)..."
	@read -p "Êtes-vous sûr? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -rf models/$(MODEL)
	@echo "✅ Modèle $(MODEL) supprimé"
	@df -h . | tail -1

models-deep-clean: ## Nettoyage profond (tous modèles + chunks + cache) - avec confirmation
	@echo "🧹 Nettoyage profond des modèles..."
	@echo "⚠️  Ceci va supprimer :"
	@echo "   - Tous les dossiers modèles dans models/"
	@echo "   - Dossiers partagés (vae, text_encoders, diffusion_models, checkpoints)"
	@echo "   - Composants partagés (clip_vision, upscale_models)"
	@echo "   - Tous les chunks (*_chunk_*)"
	@echo "   - Tous les fichiers mapping.txt"
	@echo "   - Cache HuggingFace (.cache/)"
	@read -p "Êtes-vous sûr? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@$(MAKE) _models-deep-clean-auto

_models-deep-clean-auto: ## Nettoyage profond automatique (sans confirmation) - usage interne
	@echo "🗑️  Suppression automatique..."
	@for d in models/*/; do [ -d "$$d" ] && echo "   Suppression $$d" && rm -rf "$$d"; done
	find models/ -name "*_chunk_*" -type f -delete 2>/dev/null || true
	find models/ -name "mapping.txt" -type f -delete 2>/dev/null || true
	find models/ -type d -name "chunks" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .cache/huggingface
	@echo "✅ Nettoyage profond terminé"
	@df -h . | tail -1

models-size: ## Afficher la taille des modèles locaux
	@echo "📊 Taille des modèles locaux:"
	@python -m src.model_registry list-models 2>/dev/null | while read -r line; do \
		name=$$(echo "$$line" | awk '{print $$1}'); \
		du -sh "models/$$name" 2>/dev/null || echo "   $$name: non présent"; \
	done
	@echo ""
	@echo "📊 Taille totale du dossier models:"
	@du -sh models/ 2>/dev/null || echo "   (vide)"

models-list: ## Lister les modèles locaux
	@echo "📂 Modèles locaux disponibles:"
	@ls -lh models/ 2>/dev/null || echo "Aucun modèle trouvé"

# ==================== rclone Commands (avec auto-split) ====================

rclone-check: ## Vérifier que rclone est configuré
	@which rclone > /dev/null || (echo "❌ rclone n'est pas installé"; exit 1)
	@rclone lsd owncloud:/ > /dev/null 2>&1 || (echo "❌ rclone non configuré"; exit 1)
	@echo "✅ rclone est configuré et fonctionnel"

rclone-upload: rclone-check ## Upload générique: make rclone-upload MODEL=<nom>
	@if [ -z "$(MODEL)" ]; then \
		echo "Usage: make rclone-upload MODEL=<model_name>"; \
		echo ""; echo "Modèles disponibles:"; \
		python -m src.model_registry list-models 2>/dev/null || echo "  (registre indisponible)"; exit 1; fi
	@echo "📤 Upload du modèle $(MODEL) avec découpe automatique..."
	@echo "   Fichiers >4GB seront découpés en morceaux de 2GB"
	python scripts/split_and_upload.py --model $(MODEL)
	@echo "✅ Modèle $(MODEL) uploadé"

rclone-upload-14b: rclone-check ## Alias → make rclone-upload MODEL=wan2.2-i2v-a14b
	@$(MAKE) rclone-upload MODEL=wan2.2-i2v-a14b

rclone-upload-5b: rclone-check ## Alias → make rclone-upload MODEL=wan2.2-ti2v-5b
	@$(MAKE) rclone-upload MODEL=wan2.2-ti2v-5b

rclone-upload-ltx-fast: rclone-check ## Alias → make rclone-upload MODEL=ltx-2.3-i2v-distilled
	@$(MAKE) rclone-upload MODEL=ltx-2.3-i2v-distilled

rclone-upload-ltx-pro: rclone-check ## Alias → make rclone-upload MODEL=ltx-2.3-i2v-dev
	@$(MAKE) rclone-upload MODEL=ltx-2.3-i2v-dev

rclone-upload-all: rclone-upload-14b rclone-upload-5b ## Upload TOUS les modèles WAN
	@echo "🎉 Tous les modèles WAN sont uploadés sur OwnCloud"

rclone-verify: rclone-check ## Vérifier un modèle sur OwnCloud: make rclone-verify MODEL=<nom>
	@if [ -z "$(MODEL)" ]; then echo "Usage: make rclone-verify MODEL=<model_name>"; exit 1; fi
	@echo "🔍 Vérification du modèle $(MODEL) sur OwnCloud..."
	@rclone size owncloud:/GEGM_ComfyUI/Models/$(MODEL)/ || echo "   Non trouvé"

rclone-list: rclone-check ## Lister les fichiers sur OwnCloud
	@echo "📂 Fichiers sur OwnCloud:"
	@rclone ls owncloud:/GEGM_ComfyUI/Models/

# ==================== Workflows Principaux ====================
#
# COMMANDES RECOMMANDÉES:
#   make workflow MODEL=<nom>  - Workflow complet générique
#   make workflow-5b           - Alias → make workflow MODEL=wan2.2-ti2v-5b
#   make workflow-14b          - Alias → make workflow MODEL=wan2.2-i2v-a14b
#   make workflow-wan-all      - Workflow séquentiel WAN 14B + 5B
#   make workflow-ltx-all      - Workflow séquentiel LTX Dev + Distilled
#   make workflow-all           - Workflow séquentiel TOUS les modèles
#
# Chaque workflow inclut: Download → Vérif → Split → Upload → Vérif → Deep Clean
# ========================================================================

workflow: rclone-check ## Workflow complet générique: make workflow MODEL=<nom>
	@if [ -z "$(MODEL)" ]; then \
		echo "Usage: make workflow MODEL=<model_name>"; \
		echo ""; echo "Modèles disponibles:"; \
		python -m src.model_registry list-models 2>/dev/null || echo "  (registre indisponible)"; exit 1; fi
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🚀 WORKFLOW COMPLET $(MODEL)"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "📥 1/4: Téléchargement modèle + composants..."
	./scripts/setup_wan22_native.sh $(MODEL)
	@echo ""
	@echo "📦 2/4: Découpe automatique et upload vers OwnCloud..."
	python scripts/split_and_upload.py --model $(MODEL)
	@echo ""
	@echo "🔍 3/4: Vérification de l'upload sur OwnCloud..."
	@rclone size owncloud:/GEGM_ComfyUI/Models/$(MODEL)/ || (echo "❌ Upload échoué, modèles locaux CONSERVÉS"; exit 1)
	@echo "✅ Upload vérifié avec succès"
	@echo ""
	@echo "🧹 4/4: Nettoyage profond local (deep clean)..."
	@$(MAKE) _models-deep-clean-auto
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "✅ WORKFLOW $(MODEL) TERMINÉ AVEC SUCCÈS"
	@echo "═══════════════════════════════════════════════════════════"
	@df -h . | tail -1
	@echo ""

workflow-14b: ## Alias → make workflow MODEL=wan2.2-i2v-a14b
	@$(MAKE) workflow MODEL=wan2.2-i2v-a14b

workflow-5b: ## Alias → make workflow MODEL=wan2.2-ti2v-5b
	@$(MAKE) workflow MODEL=wan2.2-ti2v-5b

workflow-ltx-fast: ## Alias → make workflow MODEL=ltx-2.3-i2v-distilled
	@$(MAKE) workflow MODEL=ltx-2.3-i2v-distilled

workflow-ltx-pro: ## Alias → make workflow MODEL=ltx-2.3-i2v-dev
	@$(MAKE) workflow MODEL=ltx-2.3-i2v-dev

workflow-ltx-all: ## Workflow séquentiel LTX Dev puis Distilled (évite surcharge disque)
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🚀 WORKFLOW SÉQUENTIEL - LTX DEV PUIS DISTILLED"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "⚠️  Exécution séquentielle pour éviter surcharge disque"
	@echo "   • Dev: Download → Upload → Deep Clean → Distilled démarre"
	@echo "   • Distilled: Download → Upload → Deep Clean → Terminé"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🔵 PHASE 1/2: LTX 2.3 Dev (22B BF16)"
	@echo "═══════════════════════════════════════════════════════════"
	@$(MAKE) workflow-ltx-pro
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🟢 PHASE 2/2: LTX 2.3 Distilled (22B FP8)"
	@echo "═══════════════════════════════════════════════════════════"
	@$(MAKE) workflow-ltx-fast
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🎉 WORKFLOW SÉQUENTIEL LTX TERMINÉ AVEC SUCCÈS"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "📊 Vérification finale des uploads sur OwnCloud:"
	@echo ""
	@echo "📦 LTX Dev:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/ltx-2.3-i2v-dev/ || echo "   Non trouvé"
	@echo ""
	@echo "📦 LTX Distilled:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/ltx-2.3-i2v-distilled/ || echo "   Non trouvé"
	@echo ""
	@echo "💾 Espace disque actuel:"
	@df -h . | tail -1
	@echo ""
	@echo "✅ Les deux modèles LTX sont uploadés et nettoyés"

workflow-wan-all: ## Workflow séquentiel WAN 14B puis 5B (évite surcharge disque)
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🚀 WORKFLOW SÉQUENTIEL - 14B PUIS 5B"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "⚠️  Exécution séquentielle pour éviter surcharge disque"
	@echo "   • 14B: Download → Upload → Deep Clean → 5B démarre"
	@echo "   • 5B: Download → Upload → Deep Clean → Terminé"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🔵 PHASE 1/2: MODÈLE 14B"
	@echo "═══════════════════════════════════════════════════════════"
	@$(MAKE) workflow-14b
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🟢 PHASE 2/2: MODÈLE 5B"
	@echo "═══════════════════════════════════════════════════════════"
	@$(MAKE) workflow-5b
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🎉 WORKFLOW SÉQUENTIEL TERMINÉ AVEC SUCCÈS"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "📊 Vérification finale des uploads sur OwnCloud:"
	@echo ""
	@echo "📦 Modèle 14B:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-i2v-a14b/
	@echo ""
	@echo "📦 Modèle 5B:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-ti2v-5b/
	@echo ""
	@echo "💾 Espace disque actuel:"
	@df -h . | tail -1
	@echo ""
	@echo "✅ Les deux modèles sont uploadés et nettoyés"

workflow-all: ## Workflow séquentiel TOUS les modèles (LTX → WAN, deep clean entre chaque)
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🚀 WORKFLOW SÉQUENTIEL - TOUS LES MODÈLES"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "⚠️  Exécution séquentielle pour éviter surcharge disque"
	@echo "   • LTX Dev → LTX Distilled → WAN 14B → WAN 5B"
	@echo "   • Deep clean entre chaque modèle"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🔵 PHASE 1/4: LTX 2.3 Dev (22B BF16)"
	@echo "═══════════════════════════════════════════════════════════"
	@$(MAKE) workflow MODEL=ltx-2.3-i2v-dev
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🔵 PHASE 2/4: LTX 2.3 Distilled (22B FP8)"
	@echo "═══════════════════════════════════════════════════════════"
	@$(MAKE) workflow MODEL=ltx-2.3-i2v-distilled
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🔵 PHASE 3/4: WAN 2.2 14B MoE"
	@echo "═══════════════════════════════════════════════════════════"
	@$(MAKE) workflow MODEL=wan2.2-i2v-a14b
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🟢 PHASE 4/4: WAN 2.2 5B"
	@echo "═══════════════════════════════════════════════════════════"
	@$(MAKE) workflow MODEL=wan2.2-ti2v-5b
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🎉 WORKFLOW SÉQUENTIEL TERMINÉ - 4 MODÈLES"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "📊 Vérification finale des uploads sur OwnCloud:"
	@echo ""
	@echo "📦 LTX Dev:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/ltx-2.3-i2v-dev/ || echo "   Non trouvé"
	@echo ""
	@echo "📦 LTX Distilled:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/ltx-2.3-i2v-distilled/ || echo "   Non trouvé"
	@echo ""
	@echo "📦 WAN 14B:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-i2v-a14b/ || echo "   Non trouvé"
	@echo ""
	@echo "📦 WAN 5B:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-ti2v-5b/ || echo "   Non trouvé"
	@echo ""
	@echo "💾 Espace disque actuel:"
	@df -h . | tail -1
	@echo ""
	@echo "✅ Les 4 modèles sont uploadés et nettoyés"

# ==================== RunPod Commands ====================

runpod-login: ## Login Docker Hub
	@echo "🔐 Docker Hub Login..."
	docker login
	@echo "✅ Logged in successfully"

runpod-verify-owncloud: ## Vérifier la connexion OwnCloud
	@echo "🔍 Vérification OwnCloud..."
	@python -c "\
from src.owncloud_config import get_owncloud_config; \
config = get_owncloud_config('default'); \
print('✅ Connexion OwnCloud OK'); \
print(f'   Serveur: {config.server_url}'); \
print(f'   Utilisateur: {config.username}'); \
print(f'   Dossier: {config.upload_folder}')" || \
	(echo "❌ Erreur connexion OwnCloud"; exit 1)

runpod-build: ## Build image multi-arch pour RunPod (AMD64 + ARM64)
	@echo "🚀 Building multi-arch RunPod image..."
	@echo "   Plateformes: linux/amd64 (RunPod), linux/arm64 (Mac)"
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		-t arnaudboy/comfy_img_to_loop:runpod \
		-t arnaudboy/comfy_img_to_loop:latest \
		--push \
		.
	@echo "✅ Image built and pushed (multi-arch)"

runpod-build-amd64-only: ## Build image AMD64 uniquement (plus rapide)
	@echo "🚀 Building AMD64-only RunPod image..."
	docker buildx build \
		--platform linux/amd64 \
		-t arnaudboy/comfy_img_to_loop:runpod \
		-t arnaudboy/comfy_img_to_loop:latest \
		--push \
		.
	@echo "✅ Image built and pushed (AMD64 only)"

runpod-setup-buildx: ## Initialiser buildx pour multi-arch
	@echo "🔧 Setup buildx..."
	docker buildx create --name multiarch --use || true
	docker buildx inspect --bootstrap
	@echo "✅ Buildx configuré"

runpod-push: ## Push vers Docker Hub
	@echo "📤 Pushing to Docker Hub..."
	docker push arnaudboy/comfy_img_to_loop:runpod
	docker push arnaudboy/comfy_img_to_loop:latest
	@echo "✅ Images pushed"

runpod-deploy: runpod-verify-owncloud runpod-setup-buildx runpod-build ## Déploiement complet
	@echo ""
	@echo "🎉 Déploiement RunPod complet !"
	@echo "📍 Image: https://hub.docker.com/r/arnaudboy/comfy_img_to_loop"
	@echo "⚠️  N'oubliez pas de configurer les variables OwnCloud sur RunPod"

runpod-deploy-quick: runpod-setup-buildx runpod-build-amd64-only ## Build AMD64 + Push (rapide)
	@echo ""
	@echo "🎉 Déploiement RunPod rapide terminé !"
	@echo "📍 Image: https://hub.docker.com/r/arnaudboy/comfy_img_to_loop"
	@echo "⚠️  N'oubliez pas de configurer les variables OwnCloud sur RunPod"

runpod-test: ## Tester localement avec GPU
	@echo "🧪 Testing with GPU..."
	docker-compose -f docker-compose.runpod.yml up

runpod-test-down: ## Arrêter le test RunPod
	docker-compose -f docker-compose.runpod.yml down

runpod-info: ## Afficher les informations RunPod
	@echo "📦 Image: arnaudboy/comfy_img_to_loop:runpod"
	@echo "🔗 Docker Hub: https://hub.docker.com/r/arnaudboy/comfy_img_to_loop"

# ==================== RunPod Commands - Image TEST ====================
# Miroir des commandes RunPod ci-dessus, mais pousse vers :test au lieu de :latest
# Usage : branche debug → make runpod-deploy-quick-test → arnaudboy/comfy_img_to_loop:test

runpod-build-test: ## Build image multi-arch TEST (AMD64 + ARM64) → :test
	@echo "🧪 Building multi-arch RunPod TEST image..."
	@echo "   Plateformes: linux/amd64 (RunPod), linux/arm64 (Mac)"
	@echo "   Tag: arnaudboy/comfy_img_to_loop:test"
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		-t arnaudboy/comfy_img_to_loop:test \
		--push \
		.
	@echo "✅ Image TEST built and pushed (multi-arch)"

runpod-build-amd64-only-test: ## Build image AMD64 uniquement TEST (plus rapide) → :test
	@echo "🧪 Building AMD64-only RunPod TEST image..."
	@echo "   Tag: arnaudboy/comfy_img_to_loop:test"
	docker buildx build \
		--platform linux/amd64 \
		-t arnaudboy/comfy_img_to_loop:test \
		--push \
		.
	@echo "✅ Image TEST built and pushed (AMD64 only)"

runpod-push-test: ## Push image TEST vers Docker Hub
	@echo "📤 Pushing TEST image to Docker Hub..."
	docker push arnaudboy/comfy_img_to_loop:test
	@echo "✅ Image TEST pushed"

runpod-deploy-test: runpod-verify-owncloud runpod-setup-buildx runpod-build-test ## Déploiement complet TEST
	@echo ""
	@echo "🧪 Déploiement RunPod TEST complet !"
	@echo "📍 Image: arnaudboy/comfy_img_to_loop:test"
	@echo "⚠️  N'oubliez pas de configurer les variables OwnCloud sur RunPod"

runpod-deploy-quick-test: runpod-setup-buildx runpod-build-amd64-only-test ## Build AMD64 + Push TEST (rapide)
	@echo ""
	@echo "🧪 Déploiement RunPod TEST rapide terminé !"
	@echo "📍 Image: arnaudboy/comfy_img_to_loop:test"
	@echo "⚠️  N'oubliez pas de configurer les variables OwnCloud sur RunPod"

runpod-test-image-test: ## Tester l'image TEST localement avec GPU
	@echo "🧪 Testing TEST image with GPU..."
	DOCKER_IMAGE=arnaudboy/comfy_img_to_loop:test docker-compose -f docker-compose.runpod.yml up

runpod-info-test: ## Afficher les informations RunPod TEST
	@echo "🧪 Image TEST: arnaudboy/comfy_img_to_loop:test"
	@echo "🔗 Docker Hub: https://hub.docker.com/r/arnaudboy/comfy_img_to_loop"
