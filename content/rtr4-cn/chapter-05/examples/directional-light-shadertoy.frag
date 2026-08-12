void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (2.0 * fragCoord - iResolution.xy) / iResolution.y;
    float radius2 = dot(uv, uv);
    if (radius2 > 1.0) {
        fragColor = vec4(0.025, 0.03, 0.04, 1.0);
        return;
    }

    vec3 normal = normalize(vec3(uv, sqrt(1.0 - radius2)));
    vec3 lightDirection = normalize(vec3(-0.5, 0.7, 0.8));
    float directLight = max(dot(normal, lightDirection), 0.0);
    vec3 surfaceColor = vec3(0.35, 0.62, 0.9);
    vec3 color = 0.08 * surfaceColor + directLight * surfaceColor;
    fragColor = vec4(color, 1.0);
}
