float distanceFalloff(float r, float maxRange) {
    float inverseSquare = 1.0 / (r * r + 0.08);
    float window = max(1.0 - pow(r / maxRange, 4.0), 0.0);
    return inverseSquare * window * window;
}

float spotlightFalloff(vec3 fromLight, vec3 spotDirection) {
    float cosine = dot(normalize(fromLight), normalize(spotDirection));
    return smoothstep(cos(0.55), cos(0.30), cosine);
}

vec3 shadeSphere(vec2 point, vec2 center, bool spotlight, vec3 lightPosition) {
    vec2 local = point - center;
    float radius2 = dot(local, local);
    if (radius2 > 0.20) return vec3(0.02, 0.025, 0.035);
    vec3 position = vec3(local, sqrt(0.20 - radius2));
    vec3 normal = normalize(position);
    vec3 toLight = lightPosition - position;
    float r = length(toLight);
    vec3 lightDirection = toLight / r;
    float attenuation = distanceFalloff(r, 2.0);
    if (spotlight) {
        vec3 spotDirection = normalize(vec3(center, 0.0) - lightPosition);
        attenuation *= spotlightFalloff(-lightDirection, spotDirection);
    }
    float lambert = max(dot(normal, lightDirection), 0.0);
    return vec3(0.04) + vec3(0.35, 0.62, 0.95) * lambert * attenuation;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (2.0 * fragCoord - iResolution.xy) / iResolution.y;
    vec2 mouse = iMouse.z > 0.0 ? (2.0 * iMouse.xy - iResolution.xy) / iResolution.y : vec2(0.0, 0.45);
    vec3 lightPosition = vec3(mouse, 1.15);
    vec3 color = uv.x < 0.0
        ? shadeSphere(uv, vec2(-0.48, 0.0), false, lightPosition)
        : shadeSphere(uv, vec2(0.48, 0.0), true, lightPosition);
    fragColor = vec4(color, 1.0);
}
