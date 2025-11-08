# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.

# Flutter wrapper
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.**  { *; }
-keep class io.flutter.util.**  { *; }
-keep class io.flutter.view.**  { *; }
-keep class io.flutter.**  { *; }
-keep class io.flutter.plugins.**  { *; }

# Supabase - Keep all classes and methods
-keep class io.supabase.** { *; }
-keepclassmembers class io.supabase.** { *; }
-dontwarn io.supabase.**

# Supabase Auth - Keep auth classes and their methods
-keep class io.supabase.auth.** { *; }
-keepclassmembers class io.supabase.auth.** { *; }
-keep class io.supabase.auth.models.** { *; }
-keepclassmembers class io.supabase.auth.models.** { *; }

# Supabase Storage - Keep storage classes for session persistence
-keep class io.supabase.storage.** { *; }
-keepclassmembers class io.supabase.storage.** { *; }

# Keep Supabase client and session classes
-keep class io.supabase.client.** { *; }
-keepclassmembers class io.supabase.client.** { *; }

# Keep all Supabase interfaces
-keep interface io.supabase.** { *; }

# Keep Supabase serialization classes
-keep class * implements io.supabase.** { *; }

# Gson
-keepattributes Signature
-keepattributes *Annotation*
-dontwarn sun.misc.**
-keep class com.google.gson.** { *; }
-keep class * implements com.google.gson.TypeAdapterFactory
-keep class * implements com.google.gson.JsonSerializer
-keep class * implements com.google.gson.JsonDeserializer

# Keep native methods
-keepclasseswithmembernames class * {
    native <methods>;
}

# Keep custom model classes
-keep class com.monytix.** { *; }

# Google Play Core (for deferred components - optional, but keep to avoid R8 errors)
-dontwarn com.google.android.play.core.**
-keep class com.google.android.play.core.** { *; }

# Flutter deferred components
-keep class io.flutter.embedding.engine.deferredcomponents.** { *; }
-dontwarn io.flutter.embedding.engine.deferredcomponents.**

