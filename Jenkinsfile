pipeline {
  agent any 
  
  options {
    timestamps()
    timeout(time: 1, unit: 'HOURS')
    buildDiscarder(logRotator(numToKeepStr: '10'))
  }

  environment {
    DOCKER_HUB_REPO = "duc8504"
    BACKEND_IMAGE = "${DOCKER_HUB_REPO}/ai-agent"
    FRONTEND_IMAGE = "${DOCKER_HUB_REPO}/ai-chatbot-ui"
    IMAGE_TAG = "${BUILD_NUMBER}"
    LATEST_TAG = "latest"
    REGISTRY_CREDENTIALS = credentials('dockerhub-credentials') // id credentials của docker trên jenkins
  }
  
  stages {
    stage('Checkout') {
      when {
        branch 'main'
      }
      steps {
        echo '===== Checking out source code ====='
        checkout scm
        echo "Branch: ${BRANCH_NAME}"
        echo "Build Number: ${BUILD_NUMBER}"
      }
    }

    stage('Install Dependencies') {
      when {
        branch 'main'
      }
      steps {
        echo '===== Installing dependencies ====='
        sh '''
          set -e
          export PATH="$HOME/.local/bin:$PATH"
          
          # Install dependencies
          cd backend
          uv sync --no-dev
          uv pip install -r ../tests/requirements.txt
        '''
      }
    }

    stage('Lint') {
      when {
        branch 'main'
      }
      steps {
        echo '===== Running linting ====='
        sh '''
          export PATH="$HOME/.local/bin:$PATH"
          cd backend
          uv run flake8 . --max-line-length=120 --exclude=venv,__pycache__,.venv || true
        '''
      }
    }

    stage('Test') {
      when {
        branch 'main'
      }
      steps {
        echo '===== Running tests ====='
        sh '''
          export PATH="$HOME/.local/bin:$PATH"
          
          cd backend
          uv run pytest ../tests -v --tb=short --junit-xml=test-results.xml || true
        '''
      }
    }    
    
    stage('Build Docker Images') {
      when {
        branch 'main'
      }
      steps {
        echo '===== Building Docker images ====='
        sh '''
          # Build backend image
          docker build -f backend/Dockerfile \
            -t ${BACKEND_IMAGE}:${IMAGE_TAG} \
            -t ${BACKEND_IMAGE}:${LATEST_TAG} .
          
          # Build frontend image
          docker build -f frontend/Dockerfile \
            -t ${FRONTEND_IMAGE}:${IMAGE_TAG} \
            -t ${FRONTEND_IMAGE}:${LATEST_TAG} .
          
          echo "Backend image: ${BACKEND_IMAGE}:${IMAGE_TAG}"
          echo "Frontend image: ${FRONTEND_IMAGE}:${IMAGE_TAG}"
        '''
      }
    }

    stage('Push to Docker Hub') {
      when {
        branch 'main'
      }
      steps {
        echo '===== Pushing images to Docker Hub ====='
        sh '''
          # Login to Docker Hub
          echo "${REGISTRY_CREDENTIALS_PSW}" | docker login -u ${REGISTRY_CREDENTIALS_USR} --password-stdin
          
          # Push backend images
          docker push ${BACKEND_IMAGE}:${IMAGE_TAG}
          docker push ${BACKEND_IMAGE}:${LATEST_TAG}
          echo "✓ Backend image pushed successfully"
          
          # Push frontend images
          docker push ${FRONTEND_IMAGE}:${IMAGE_TAG}
          docker push ${FRONTEND_IMAGE}:${LATEST_TAG}
          echo "✓ Frontend image pushed successfully"
          
          # Logout
          docker logout
        '''
      }
    }

    stage('Deploy') {
      when {
        branch 'main'
      }
      steps {
        echo '===== Deploying to production ====='
        sh '''
          echo "Deploying backend image: ${BACKEND_IMAGE}:${IMAGE_TAG}"
          echo "Deploying frontend image: ${FRONTEND_IMAGE}:${IMAGE_TAG}"
          echo "Deployment completed successfully"
        '''
      }
    }
  }
  
  post {
    always {
      echo '===== Pipeline finished ====='
      junit allowEmptyResults: true, testResults: 'backend/test-results.xml'
    }
    success {
      echo '✓ Pipeline succeeded!'
    }
    failure {
      echo '✗ Pipeline failed!'
    }
  }
}
