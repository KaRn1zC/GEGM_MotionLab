.PHONY: help build up down restart logs shell test clean

# Variables
DOCKER_COMPOSE = docker-compose
IMAGE_NAME = comfy_img_to_loop
CONTAINER_NAME = comfy_img_to_loop

help: ## Afficher cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-35s\033[0m %s\n", $$1, $$2}'

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

download-models: ## Télécharger les modèles WAN 2.2 localement
	@echo "📥 Téléchargement des modèles..."
	./scripts/setup_wan22_native.sh

test-download-models: ## Tester le téléchargement depuis OwnCloud
	@echo "🧪 Test téléchargement OwnCloud..."
	python scripts/download_models_from_owncloud.py --model wan2.2-i2v-a14b --target-dir ./test_models
	@echo "✅ Test terminé - vérifiez ./test_models/"

models-clean: ## Supprimer les modèles locaux (libère 117GB)
	@echo "🗑️  Nettoyage des modèles locaux..."
	@echo "⚠️  Ceci va supprimer :"
	@echo "   - models/wan2.2-i2v-a14b (28GB)"
	@echo "   - models/wan2.2-ti2v-5b (9GB)"
	@echo "   Total: ~117GB libérés"
	@read -p "Êtes-vous sûr? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo "🧹 Suppression..."
	rm -rf models/wan2.2-i2v-a14b
	rm -rf models/wan2.2-ti2v-5b
	@echo "✅ Modèles supprimés"
	@df -h . | tail -1

models-deep-clean: ## Nettoyage profond (modèles + chunks + cache) - avec confirmation
	@echo "🧹 Nettoyage profond des modèles..."
	@echo "⚠️  Ceci va supprimer :"
	@echo "   - Tous les modèles dans models/"
	@echo "   - models/vae/, models/text_encoders/, models/diffusion_models/"
	@echo "   - models/clip_vision/, models/upscale_models/"
	@echo "   - Tous les chunks (*_chunk_*)"
	@echo "   - Tous les fichiers mapping.txt"
	@echo "   - Cache HuggingFace (.cache/)"
	@read -p "Êtes-vous sûr? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@$(MAKE) _models-deep-clean-auto

_models-deep-clean-auto: ## Nettoyage profond automatique (sans confirmation) - usage interne
	@echo "🗑️  Suppression automatique..."
	rm -rf models/wan2.2-i2v-a14b
	rm -rf models/wan2.2-ti2v-5b
	rm -rf models/vae
	rm -rf models/text_encoders
	rm -rf models/diffusion_models
	rm -rf models/clip_vision
	rm -rf models/upscale_models
	find models/ -name "*_chunk_*" -type f -delete 2>/dev/null || true
	find models/ -name "mapping.txt" -type f -delete 2>/dev/null || true
	find models/ -type d -name "chunks" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .cache/huggingface
	@echo "✅ Nettoyage profond terminé"
	@df -h . | tail -1

models-size: ## Afficher la taille des modèles locaux
	@echo "📊 Taille des modèles locaux:"
	@du -sh models/wan2.2-i2v-a14b 2>/dev/null || echo "   wan2.2-i2v-a14b: non présent"
	@du -sh models/wan2.2-ti2v-5b 2>/dev/null || echo "   wan2.2-ti2v-5b: non présent"
	@echo ""
	@echo "📊 Taille totale du dossier models:"
	@du -sh models/

models-list: ## Lister les modèles locaux
	@echo "📂 Modèles locaux disponibles:"
	@ls -lh models/ 2>/dev/null || echo "Aucun modèle trouvé"

# ==================== rclone Commands (avec auto-split) ====================

rclone-check: ## Vérifier que rclone est configuré
	@which rclone > /dev/null || (echo "❌ rclone n'est pas installé"; exit 1)
	@rclone lsd owncloud:/ > /dev/null 2>&1 || (echo "❌ rclone non configuré"; exit 1)
	@echo "✅ rclone est configuré et fonctionnel"

rclone-upload-14b: rclone-check ## Upload modèle 14B ComfyUI Native (découpe auto >4GB)
	@echo "📤 Upload du modèle 14B ComfyUI Native avec découpe automatique..."
	@echo "   Fichiers >4GB seront découpés en morceaux de 2GB"
	python scripts/split_and_upload.py --model wan2.2-i2v-a14b
	@echo "✅ Modèle 14B uploadé"

rclone-upload-5b: rclone-check ## Upload modèle 5B ComfyUI Native (découpe auto >4GB)
	@echo "📤 Upload du modèle 5B ComfyUI Native avec découpe automatique..."
	@echo "   Fichiers >4GB seront découpés en morceaux de 2GB"
	python scripts/split_and_upload.py --model wan2.2-ti2v-5b
	@echo "✅ Modèle 5B uploadé"

rclone-upload-all: rclone-upload-14b rclone-upload-5b ## Upload TOUS les modèles
	@echo "🎉 Tous les modèles sont uploadés sur OwnCloud"

rclone-verify: rclone-check ## Vérifier les fichiers sur OwnCloud
	@echo "🔍 Vérification des modèles sur OwnCloud..."
	@echo ""
	@echo "📦 Modèle 14B:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-i2v-a14b/ || echo "   Non trouvé"
	@echo ""
	@echo "📦 Modèle 5B:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-ti2v-5b/ || echo "   Non trouvé"

rclone-list: rclone-check ## Lister les fichiers sur OwnCloud
	@echo "📂 Fichiers sur OwnCloud:"
	@rclone ls owncloud:/GEGM_ComfyUI/Models/

# ==================== Workflows Principaux ====================
#
# COMMANDES RECOMMANDÉES:
#   make workflow-5b     - Workflow complet modèle 5B
#   make workflow-14b    - Workflow complet modèle 14B
#   make workflow-both   - Workflow séquentiel 14B + 5B (évite surcharge disque)
#
# Chaque workflow inclut: Download → Vérif → Split → Upload → Vérif → Deep Clean
# ========================================================================

workflow-14b: rclone-check ## [PRINCIPAL] Workflow complet 14B: Download → Vérif → Split → Upload → Vérif → Deep Clean
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🚀 WORKFLOW COMPLET MODÈLE 14B"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "📥 1/6: Téléchargement modèle 14B + composants (ComfyUI Native)..."
	@echo "      • Diffusion models FP16 (2x28.6 GB)"
	@echo "      • T5 Encoder FP16 (11.4 GB)"
	@echo "      • VAE 14B (254 MB)"
	@echo "      • CLIP Vision (2.4 GB)"
	@echo "      • Upscalers (UltraSharp + RealESRGAN)"
	@echo "      • Vérifications intégrité automatiques"
	./scripts/setup_wan22_native.sh wan2.2-i2v-a14b
	@echo ""
	@echo "📦 2/6: Découpe automatique et upload vers OwnCloud..."
	@echo "      • Fichiers >4GB découpés en chunks 2GB"
	@echo "      • Suppression automatique des originaux"
	@echo "      • Upload de tous les fichiers (via symlinks)"
	python scripts/split_and_upload.py --model wan2.2-i2v-a14b
	@echo ""
	@echo "🔍 3/6: Vérification de l'upload sur OwnCloud..."
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-i2v-a14b/ || (echo "❌ Upload échoué, modèles locaux CONSERVÉS"; exit 1)
	@echo "✅ Upload vérifié avec succès"
	@echo ""
	@echo "🧹 4/6: Nettoyage profond local (deep clean)..."
	@$(MAKE) _models-deep-clean-auto
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "✅ WORKFLOW 14B TERMINÉ AVEC SUCCÈS"
	@echo "═══════════════════════════════════════════════════════════"
	@df -h . | tail -1
	@echo ""

workflow-5b: rclone-check ## [PRINCIPAL] Workflow complet 5B: Download → Vérif → Split → Upload → Vérif → Deep Clean
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🚀 WORKFLOW COMPLET MODÈLE 5B"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "📥 1/6: Téléchargement modèle 5B + composants (ComfyUI Native)..."
	@echo "      • Diffusion model FP16 (9.31 GB)"
	@echo "      • T5 Encoder FP16 (11.4 GB)"
	@echo "      • VAE 5B (254 MB)"
	@echo "      • CLIP Vision (2.4 GB)"
	@echo "      • Upscalers (UltraSharp + RealESRGAN)"
	@echo "      • Vérifications intégrité automatiques"
	./scripts/setup_wan22_native.sh wan2.2-ti2v-5b
	@echo ""
	@echo "📦 2/6: Découpe automatique et upload vers OwnCloud..."
	@echo "      • Fichiers >4GB découpés en chunks 2GB"
	@echo "      • Suppression automatique des originaux"
	@echo "      • Upload de tous les fichiers (via symlinks)"
	python scripts/split_and_upload.py --model wan2.2-ti2v-5b
	@echo ""
	@echo "🔍 3/6: Vérification de l'upload sur OwnCloud..."
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-ti2v-5b/ || (echo "❌ Upload échoué, modèles locaux CONSERVÉS"; exit 1)
	@echo "✅ Upload vérifié avec succès"
	@echo ""
	@echo "🧹 4/6: Nettoyage profond local (deep clean)..."
	@$(MAKE) _models-deep-clean-auto
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "✅ WORKFLOW 5B TERMINÉ AVEC SUCCÈS"
	@echo "═══════════════════════════════════════════════════════════"
	@df -h . | tail -1
	@echo ""

workflow-both: ## [PRINCIPAL] Workflow séquentiel 14B puis 5B (évite surcharge disque)
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
