# ─── ROAS Engine — GCP Cloud Run Deployment ───
# Terraform config for deploying the engine to Google Cloud.

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "roas-engine-terraform-state"
    prefix = "terraform/state"
  }
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "asia-southeast1"
}

variable "db_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─── Cloud SQL (PostgreSQL) ───

resource "google_sql_database_instance" "roas_db" {
  name             = "roas-engine-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = "db-f1-micro"  # Start small, scale up
    availability_type = "ZONAL"

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        name  = "allow-cloud-run"
        value = "0.0.0.0/0"  # Restrict in production
      }
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "roas" {
  name     = "roas_engine"
  instance = google_sql_database_instance.roas_db.name
}

resource "google_sql_user" "roas_user" {
  name     = "roas"
  instance = google_sql_database_instance.roas_db.name
  password = var.db_password
}

# ─── Redis (Memorystore) ───

resource "google_redis_instance" "roas_cache" {
  name           = "roas-engine-cache"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
  redis_version  = "REDIS_7_0"
}

# ─── Artifact Registry ───

resource "google_artifact_registry_repository" "roas" {
  location      = var.region
  repository_id = "roas-engine"
  format        = "DOCKER"
}

# ─── Cloud Run — Backend ───

resource "google_cloud_run_v2_service" "backend" {
  name     = "roas-engine-backend"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/roas-engine/backend:latest"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "DATABASE_URL"
        value = "postgresql+asyncpg://roas:${var.db_password}@${google_sql_database_instance.roas_db.ip_address.0.ip_address}:5432/roas_engine"
      }

      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.roas_cache.host}:${google_redis_instance.roas_cache.port}/0"
      }

      # Platform credentials from Secret Manager
      dynamic "env" {
        for_each = [
          "GOOGLE_ADS_DEVELOPER_TOKEN",
          "GOOGLE_ADS_CLIENT_ID",
          "GOOGLE_ADS_CLIENT_SECRET",
          "GOOGLE_ADS_REFRESH_TOKEN",
          "GOOGLE_ADS_CUSTOMER_ID",
          "META_APP_ID",
          "META_APP_SECRET",
          "META_ACCESS_TOKEN",
          "META_AD_ACCOUNT_ID",
        ]
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = "roas-engine-${lower(replace(env.value, "_", "-"))}"
              version = "latest"
            }
          }
        }
      }
    }

    scaling {
      min_instance_count = 1  # Always on for the scheduler
      max_instance_count = 1  # Single instance (scheduler state)
    }
  }
}

# ─── Cloud Run — Frontend ───

resource "google_cloud_run_v2_service" "frontend" {
  name     = "roas-engine-dashboard"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/roas-engine/frontend:latest"

      ports {
        container_port = 80
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }
}

# ─── IAM — Allow public access to frontend ───

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ─── Outputs ───

output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  value = google_cloud_run_v2_service.frontend.uri
}

output "database_ip" {
  value = google_sql_database_instance.roas_db.ip_address.0.ip_address
}

output "redis_host" {
  value = google_redis_instance.roas_cache.host
}
