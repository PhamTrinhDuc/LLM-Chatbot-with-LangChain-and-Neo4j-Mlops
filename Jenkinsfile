pipeline {
  agent any 
  
  options {
    timestamps()
    timeout(time: 1, unit: 'HOURS')
  }
  
  stages {
    stage('Checkout') {
      when {
        branch 'main'
      }
      steps {
        echo 'Checking out source code...'
        checkout scm
      }
    }

    stage('Install Dependencies') {
      when {
        branch 'main'
      }
      steps {
        echo 'Installing dependencies...'
        sh '''
          cd backend
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r ../tests/requirements.txt
        '''
      }
    }

    stage('Lint') {
      when {
        branch 'main'
      }
      steps {
        echo 'Linting code...'
        sh '''
          pip install pylint flake8
          python -m flake8 backend/ --max-line-length=120 --exclude=venv,__pycache__
        '''
      }
    }

    stage('Test') {
      when {
        branch 'main'
      }
      steps {
        echo 'Running tests...'
        sh '''
          cd backend
          pytest -v --tb=short --junitxml=test-results.xml
        '''
      }
    }

    stage('Deploy') {
      when {
        branch 'main'
      }
      steps {
        echo 'Deploying to production...'
        sh 'echo "Deployment completed"'
      }
    }
  }
  
  post {
    always {
      echo 'Pipeline finished'
    }
    success {
      echo 'Pipeline succeeded!'
    }
    failure {
      echo 'Pipeline failed!'
    }
  }
}
