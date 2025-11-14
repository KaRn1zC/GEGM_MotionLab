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

models-deep-clean: ## Nettoyage profond (modèles + chunks + cache)
	@echo "🧹 Nettoyage profond des modèles..."
	@echo "⚠️  Ceci va supprimer :"
	@echo "   - Tous les modèles dans models/"
	@echo "   - Tous les chunks (*_chunk_*)"
	@echo "   - Tous les fichiers mapping.txt"
	@echo "   - Cache HuggingFace (.cache/)"
	@read -p "Êtes-vous sûr? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo "🗑️  Suppression..."
	rm -rf models/wan2.2-i2v-a14b
	rm -rf models/wan2.2-ti2v-5b
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

# ==================== VAE Conversion ====================

convert-vae-channels-5b: ## Convertir VAE 96ch → 48ch (modèle 5B)
	@echo "🔄 Conversion VAE WAN 5B (96ch → 48ch)..."
	python scripts/convert_vae_channels.py wan2.2-ti2v-5b
	@echo "✅ Conversion terminée"


convert-vae-channels-14b: ## Convertir VAE 96ch → 48ch (modèle 14B)
	@echo "🔄 Conversion VAE WAN 14B (96ch → 48ch)..."
	python scripts/convert_vae_channels.py wan2.2-i2v-a14b
	@echo "✅ Conversion terminée"

# ==================== rclone Commands (avec auto-split) ====================

rclone-check: ## Vérifier que rclone est configuré
	@which rclone > /dev/null || (echo "❌ rclone n'est pas installé"; exit 1)
	@rclone lsd owncloud:/ > /dev/null 2>&1 || (echo "❌ rclone non configuré"; exit 1)
	@echo "✅ rclone est configuré et fonctionnel"

rclone-upload-14b: rclone-check convert-vae-channels-14b ## Upload modèle 14B (découpe auto >8GB et VAE converti)
	@echo "📤 Upload du modèle 14B avec découpe automatique et VAE corrigé..."
	@echo "   Fichiers >8GB seront découpés en morceaux de 2GB"
	python scripts/split_and_upload.py --model wan2.2-i2v-a14b
	@echo "✅ Modèle 14B uploadé"

rclone-upload-5b: rclone-check convert-vae-channels-5b ## Upload modèle 5B (découpe auto >8GB et VAE converti)
	@echo "📤 Upload du modèle 5B avec découpe automatique et VAE corrigé..."
	@echo "   Fichiers >8GB seront découpés en morceaux de 2GB"
	python scripts/split_and_upload.py --model wan2.2-ti2v-5b
	@echo "✅ Modèle 5B uploadé"

rclone-upload-reassemble-script: ## Upload le script de reconstitution
	@echo "📤 Upload du script de reconstitution..."
	@chmod +x scripts/reassemble_models.sh
	rclone copy scripts/reassemble_models.sh owncloud:/GEGM_ComfyUI/scripts/
	@echo "✅ Script uploadé"

rclone-upload-all: rclone-upload-14b rclone-upload-5b rclone-upload-reassemble-script ## Upload TOUS les modèles
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

# ==================== Workflow Complet ====================

full-upload-workflow: download-models rclone-upload-all models-clean ## Workflow complet
	@echo ""
	@echo "🎉 Workflow complet terminé !"
	@echo "✅ Modèles téléchargés, découpés et uploadés sur OwnCloud"
	@echo "✅ Modèles locaux supprimés (~117GB libérés)"
	@df -h . | tail -1

# ==================== Sequential Upload (Low Disk Space) ====================

full-workflow-14b: rclone-check ## 14B: Download → Convert VAE → Split (delete originals) → Upload (chunks only) → Verify → Clean
	@echo "🔄 Workflow complet modèle 14B (download → convert VAE → split (delete originals) → upload (chunks) → verify → clean)"
	@echo ""
	@echo "📥 1/6: Téléchargement du modèle 14B..."
	./scripts/setup_wan22_native.sh wan2.2-i2v-a14b
	@echo ""
	@echo "🔄 2/6: Conversion VAE (96ch → 48ch)..."
	python scripts/convert_vae_channels.py wan2.2-i2v-a14b
	@echo ""
	@echo "📦 3/6: Découpe et upload du modèle 14B..."
	python scripts/split_and_upload.py --model wan2.2-i2v-a14b
	@echo ""
	@echo "🔍 4/6: Vérification de l'upload..."
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-i2v-a14b/ || (echo "❌ Upload échoué, modèles locaux CONSERVÉS"; exit 1)
	@echo ""
	@echo "✅ 5/6: Upload vérifié, nettoyage local..."
	rm -rf models/wan2.2-i2v-a14b
	@echo ""
	@echo "✅ 6/6: Modèle 14B uploadé et nettoyé"
	@df -h . | tail -1

full-workflow-5b: rclone-check ## 5B: Download → Convert VAE → Split (delete originals) → Upload (chunks only) → Verify → Clean
	@echo "🔄 Workflow complet modèle 5B (download → convert VAE → split (delete originals) → upload (chunks) → verify → clean)"
	@echo ""
	@echo "📥 1/6: Téléchargement du modèle 5B..."
	./scripts/setup_wan22_native.sh wan2.2-ti2v-5b
	@echo ""
	@echo "🔄 2/6: Conversion VAE (96ch → 48ch)..."
	python scripts/convert_vae_channels.py wan2.2-ti2v-5b
	@echo ""
	@echo "📦 3/6: Découpe et upload du modèle 5B..."
	python scripts/split_and_upload.py --model wan2.2-ti2v-5b
	@echo ""
	@echo "🔍 4/6: Vérification de l'upload..."
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-ti2v-5b/ || (echo "❌ Upload échoué, modèles locaux CONSERVÉS"; exit 1)
	@echo ""
	@echo "✅ 5/6: Upload vérifié, nettoyage local..."
	rm -rf models/wan2.2-ti2v-5b
	@echo ""
	@echo "✅ 6/6: Modèle 5B uploadé et nettoyé"
	@df -h . | tail -1

sequential-upload-workflow: full-workflow-14b full-workflow-5b rclone-upload-reassemble-script ## Workflow séquentiel (espace disque limité <54GB)
	@echo ""
	@echo "🎉 Workflow séquentiel terminé !"
	@echo "✅ Modèle 14B uploadé et nettoyé (~28GB)"
	@echo "✅ Modèle 5B uploadé et nettoyé (~9GB)"
	@echo "✅ Script de reconstitution uploadé"
	@echo ""
	@echo "📊 Vérification finale:"
	@echo ""
	@echo "📦 Modèle 14B:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-i2v-a14b/
	@echo ""
	@echo "📦 Modèle 5B:"
	@rclone size owncloud:/GEGM_ComfyUI/Models/wan2.2-ti2v-5b/
	@echo ""
	@echo "💾 Espace disque actuel:"
	@df -h . | tail -1

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
