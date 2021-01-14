// Jenkinsfile for etcd3_model Python package
// Copyright 2019, Cray Inc. All rights reserved.

@Library('dst-shared@master') _

pipeline {
    agent {
        kubernetes {
            label "etcd3-model-python-pod"
            containerTemplate {
                name "etcd3-model-python-pod"
                image "dtr.dev.cray.com/cray/cray-cms-python3-build:latest"
                ttyEnabled true
                command "cat"
                alwaysPullImage true
            }
        }
    }

    // Configuration options applicable to the entire job
    options {
        // This build should not take long, fail the build if it appears stuck
        timeout(time: 15, unit: 'MINUTES')

        // Don't fill up the build server with unnecessary cruft
        buildDiscarder(logRotator(numToKeepStr: '5'))

        // Add timestamps and color to console output, cuz pretty
        timestamps()
    }

    stages {
        stage('Unit Tests') {
            steps {
                container('etcd3-model-python-pod') {
                    // gcc, g++, python3-dev and linux-heades are needed
                    // for testing because grpcio has to be built when
                    // it is installed.
                    sh """
                        apk add --no-cache gcc g++ python3-dev linux-headers
                        pip3 install nox
                        nox
                    """
                }
            }
        }
        stage('Build Package') {
            steps {
                container('etcd3-model-python-pod') {
                    sh """
                        pip3 install wheel
                        python3 setup.py sdist bdist_wheel
                    """
                }
            }
        }

        stage('PUBLISH') {
            when { branch 'master'}
            steps {
                container('etcd3-model-python-pod') {
                    // Need to install ssh and rsync commands, the keys are
                    // already in the image.  For some reason bash and curl
                    // make transferPkg not fail with a complaint about a
                    // missing file.  See DST-6595 for more info.
                    sh """
                        apk add --no-cache openssh-client rsync sshpass bash curl
                    """
                    transferPkgs(directory: "etcd3-model", artifactName: "dist/*.tar.gz")
                    transferPkgs(directory: "etcd3-model", artifactName: "dist/*.whl")
                }
            }
        }
    }

    post('Post-build steps') {
        failure {
            emailext (
                subject: "FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
                body: """<p>FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
                <p>Check console output at &QUOT;<a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a>&QUOT;</p>""",
                recipientProviders: [[$class: 'CulpritsRecipientProvider'], [$class: 'RequesterRecipientProvider']]
            )
        }

        success {
            archiveArtifacts artifacts: 'dist/*', fingerprint: true
        }
    }
}
