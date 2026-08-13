#version 450

layout(location = 0) out vec4 outColor;

float distanceFalloff(float distanceToLight, float maxRange) {
    float inverseSquare = 1.0 / (distanceToLight * distanceToLight + 0.08);
    float window = max(1.0 - pow(distanceToLight / maxRange, 4.0), 0.0);
    return inverseSquare * window * window;
}

float spotlightFalloff(vec3 fromLight, vec3 spotDirection) {
    float cosine = dot(normalize(fromLight), normalize(spotDirection));
    return smoothstep(cos(0.55), cos(0.30), cosine);
}

vec3 shadeSphere(vec2 point, vec2 center, bool spotlight) {
    vec2 local = point - center;
    float radius2 = dot(local, local);
    if (radius2 > 0.20) {
        return vec3(0.02, 0.025, 0.035);
    }
    vec3 position = vec3(local, sqrt(0.20 - radius2));
    vec3 normal = normalize(position);
    vec3 lightPosition = vec3(0.0, 0.45, 1.15);
    vec3 toLight = lightPosition - position;
    float distanceToLight = length(toLight);
    vec3 lightDirection = toLight / distanceToLight;
    float attenuation = distanceFalloff(distanceToLight, 2.0);
    if (spotlight) {
        attenuation *= spotlightFalloff(-lightDirection, vec3(center.x, -0.45, -1.15));
    }
    float lambert = max(dot(normal, lightDirection), 0.0);
    return vec3(0.04) + vec3(0.35, 0.62, 0.95) * lambert * attenuation;
}

void main() {
    vec2 uv = gl_FragCoord.xy / vec2(800.0, 600.0) * 2.0 - 1.0;
    uv.x *= 800.0 / 600.0;
    vec3 color = uv.x < 0.0
        ? shadeSphere(uv, vec2(-0.48, 0.0), false)
        : shadeSphere(uv, vec2(0.48, 0.0), true);
    outColor = vec4(color, 1.0);
}
