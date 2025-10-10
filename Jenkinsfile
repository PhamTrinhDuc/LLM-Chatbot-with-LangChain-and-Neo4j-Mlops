pipeline {
  agent any 
  stages {
    stage('Checkout') {
      steps {
        echo 'Checking out source code...'
        checkout scm // tự động checkout đúng nhánh đang build
      }
    }
    stage('Install Dependencies') {
      steps {
        echo 'Installing dependencies...'
      }
    }

    stage('Lint') {
      steps {
        echo 'Linting code...'
      }
    }

    stage('Test') {
      steps {
        echo 'Running tests...'
      }
    }

    // Chỉ deploy nếu là nhánh main
    stage('Deploy') {
        when {
            branch 'main'  // Chỉ chạy khi nhánh là main
        }
        steps {
            sh 'echo "Deploying to production..."'
        }
    }
}
