import java.io.File

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Supplied by the publishing owner's secret mechanism, never checked-in properties.
val uploadStorePath = providers.environmentVariable("SELAHCUE_UPLOAD_STORE_FILE").orNull
val uploadStorePassword = providers.environmentVariable("SELAHCUE_UPLOAD_STORE_PASSWORD").orNull
val uploadKeyAlias = providers.environmentVariable("SELAHCUE_UPLOAD_KEY_ALIAS").orNull
val uploadKeyPassword = providers.environmentVariable("SELAHCUE_UPLOAD_KEY_PASSWORD").orNull
val uploadStore = uploadStorePath?.takeIf { it.isNotBlank() }?.let { file(it) }
val checkoutRoot = rootProject.projectDir.resolve("../../../..").canonicalFile

val validateUploadSigning = tasks.register("validateUploadSigning") {
    group = "verification"
    description = "Reject release builds without explicit upload signing configuration."
    doLast {
        if (listOf(uploadStorePath, uploadStorePassword, uploadKeyAlias, uploadKeyPassword)
                .any { it.isNullOrBlank() }) {
            throw GradleException("Upload signing configuration is incomplete. See docs/release/mobile/ANDROID-UPLOAD-SIGNING.md.")
        }
        if (uploadStorePath?.let { File(it).isAbsolute } != true || uploadStore?.isFile != true
                || uploadStore.canonicalFile.toPath().startsWith(checkoutRoot.toPath())) {
            throw GradleException("Upload signing keystore must be an existing absolute file outside the checkout.")
        }
    }
}

android {
    namespace = "com.selahcue.selahcue_controller"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.selahcue.selahcue_controller"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("upload") {
            storeFile = uploadStore
            storePassword = uploadStorePassword
            keyAlias = uploadKeyAlias
            keyPassword = uploadKeyPassword
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("upload")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

// Covers release APK/AAB and mixed task invocations; debug-only graphs stay usable.
tasks.matching { it.name == "preReleaseBuild" }.configureEach {
    dependsOn(validateUploadSigning)
}
