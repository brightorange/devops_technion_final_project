// CI for the application repo: lint, test, scan, build, publish.
// Deployment lives in the infra repo's pipeline, which owns the Helm chart.
pipeline {
    agent any

    environment {
        // Jenkins runs under launchd, which supplies an empty PATH. Naming the
        // toolchain explicitly also makes the pipeline's dependencies visible
        // instead of inheriting whatever happens to be in a shell profile.
        PATH  = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        IMAGE = "shop-api"
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Prepare') {
            steps {
                script {
                    // Tag by commit so every build is uniquely identifiable and
                    // Kubernetes is forced to pull rather than reuse a cached
                    // image under an unchanged tag.
                    env.TAG = sh(script: 'git rev-parse --short HEAD',
                                 returnStdout: true).trim()
                }
                echo "Building ${env.IMAGE}:${env.TAG}"
            }
        }

        // ---- Security gate 1: secrets ----
        // Scans the whole git history, not just the checkout: a credential that
        // was committed and later deleted is still a leaked credential.
        stage('Secret scan') {
            steps {
                sh 'gitleaks detect --source . --redact --no-banner'
            }
        }

        stage('Build test image') {
            steps {
                sh 'docker build --target test -t "$IMAGE:test" backend'
            }
        }

        stage('Lint') {
            steps {
                sh 'docker run --rm "$IMAGE:test" flake8'
            }
        }

        stage('Test') {
            steps {
                sh 'mkdir -p reports'
                // Tests run inside the image so they execute against the exact
                // Python and dependency set that ships.
                sh '''
                    docker run --rm -v "$WORKSPACE/reports:/out" "$IMAGE:test" \
                        pytest -q \
                            --junitxml=/out/report.xml \
                            --cov-report=xml:/out/coverage.xml
                '''
            }
            post {
                always {
                    junit 'reports/report.xml'
                }
            }
        }

        stage('Build image') {
            steps {
                sh 'docker build --target runtime -t "$IMAGE:$TAG" backend'
            }
        }

        // ---- Security gate 2: image vulnerabilities ----
        // --ignore-unfixed is deliberate. The base image carries ~50 HIGH/CRITICAL
        // CVEs with no upstream patch available; failing on those would make the
        // gate unsatisfiable, and an unsatisfiable gate gets switched off. The
        // build fails on what can actually be remediated.
        stage('Image scan') {
            steps {
                sh '''
                    trivy image \
                        --scanners vuln \
                        --severity HIGH,CRITICAL \
                        --ignore-unfixed \
                        --exit-code 1 \
                        --no-progress \
                        "$IMAGE:$TAG"
                '''
            }
        }

        // Minikube keeps its own image store, so a locally built image has to be
        // side-loaded before the cluster can run it. Replaced by a registry push
        // once the cloud environment exists.
        stage('Publish to Minikube') {
            when { branch 'main' }
            steps {
                sh 'docker tag "$IMAGE:$TAG" "$IMAGE:dev"'
                sh 'minikube image load "$IMAGE:dev"'
            }
        }
    }

    post {
        always {
            // The test image is rebuilt every run and is not deployed anywhere.
            sh 'docker image rm -f "$IMAGE:test" || true'
        }
    }
}
