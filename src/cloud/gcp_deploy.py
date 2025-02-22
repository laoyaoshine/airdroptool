from google.cloud import run_v2, storage
import subprocess
from ..core.tools import log, handle_error

def deploy_to_gcp(project_id: str = "your-project", location: str = "us-central1", instance_count: int = 5):
    """优化部署到 Google Cloud Run，支持自动缩放和错误处理"""
    try:
        # 构建 Docker 镜像
        subprocess.run(["gcloud", "builds", "submit", "--tag", f"gcr.io/{project_id}/airdrop-tool"], check=True)

        # 部署到 Cloud Run
        client = run_v2.ServicesClient()
        service = run_v2.Service()
        service.template.containers[0].image = f"gcr.io/{project_id}/airdrop-tool"
        service.template.scaling.minimum_instance_count = 1
        service.template.scaling.maximum_instance_count = instance_count
        service.template.scaling.target_utilization = 0.7  # 目标 CPU 利用率 70%
        service.template.containers[0].env.append(run_v2.EnvVar(name="NUM_INSTANCES", value=str(instance_count)))
        response = client.create_service(
            request={"parent": f"projects/{project_id}/locations/{location}", "service": service, "service_id": "airdrop-service"}
        )
        log(f"Deployed to Cloud Run: {response.name}")
    except Exception as e:
        handle_error(e, "GCP deployment")

if __name__ == "__main__":
    deploy_to_gcp()