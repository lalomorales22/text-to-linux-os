"""
AI-powered error handler for build failures
"""
import logging
import re
from typing import Dict, Any, Optional, List
import anthropic
import os

logger = logging.getLogger(__name__)


class BuildErrorAnalyzer:
    """Analyzes build errors using Claude AI and suggests fixes"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def analyze_build_error(self, logs: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze build error logs and suggest fixes
        Returns: {
            "error_type": str,
            "description": str,
            "suggested_fix": str,
            "modified_config": dict (optional)
        }
        """
        try:
            # Extract error messages from logs
            errors = self._extract_errors(logs)

            if not errors:
                return {
                    "error_type": "unknown",
                    "description": "Build failed but no specific error found in logs",
                    "suggested_fix": "Check the complete build logs for details"
                }

            # Build prompt for Claude
            prompt = self._build_analysis_prompt(errors, config)

            # Get analysis from Claude
            message = self.client.messages.create(
                model="claude-opus-4-5-20251101",
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse response
            response_text = message.content[0].text
            return self._parse_analysis_response(response_text, config)

        except Exception as e:
            logger.error(f"Error analyzing build failure: {e}", exc_info=True)
            return {
                "error_type": "analysis_failed",
                "description": f"Failed to analyze error: {str(e)}",
                "suggested_fix": "Please check logs manually"
            }

    def _extract_errors(self, logs: str) -> List[str]:
        """Extract error messages from build logs"""
        errors = []

        # Common error patterns
        error_patterns = [
            r'E: (.+)',  # apt errors
            r'ERROR: (.+)',  # General errors
            r'FATAL: (.+)',  # Fatal errors
            r'Package (.+) not found',  # Package not found
            r'Unable to locate package (.+)',  # Package not available
            r'Depends: (.+) but it is not going to be installed',  # Dependency issues
            r'Failed to fetch (.+)',  # Download failures
        ]

        for pattern in error_patterns:
            matches = re.findall(pattern, logs, re.MULTILINE)
            errors.extend(matches)

        # Return unique errors
        return list(set(errors))[:10]  # Limit to 10 most unique errors

    def _build_analysis_prompt(self, errors: List[str], config: Dict[str, Any]) -> str:
        """Build prompt for Claude to analyze errors"""
        packages_list = ", ".join(config.get('packages', []))

        prompt = f"""You are analyzing a Debian live-build ISO build failure.

Build Configuration:
- Distribution: Debian Bookworm
- Architecture: amd64
- Packages requested: {packages_list}

Errors found in build logs:
{chr(10).join(f"- {error}" for error in errors)}

Please analyze these errors and provide:
1. The type of error (package_not_found, dependency_conflict, download_failure, etc.)
2. A clear description of what went wrong
3. A specific suggested fix

If the issue is a package name error, suggest the correct package name.
If it's a dependency conflict, suggest which packages to remove or alternatives.
If it's a download failure, suggest retry or alternative mirrors.

Format your response as:
ERROR_TYPE: <type>
DESCRIPTION: <description>
SUGGESTED_FIX: <fix>
REPLACEMENT_PACKAGES: <package1, package2> (if applicable)
"""

        return prompt

    def _parse_analysis_response(self, response: str, original_config: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Claude's analysis response"""
        result = {
            "error_type": "unknown",
            "description": "",
            "suggested_fix": "",
            "modified_config": None
        }

        # Extract error type
        error_type_match = re.search(r'ERROR_TYPE:\s*(.+)', response)
        if error_type_match:
            result["error_type"] = error_type_match.group(1).strip()

        # Extract description
        desc_match = re.search(r'DESCRIPTION:\s*(.+)', response)
        if desc_match:
            result["description"] = desc_match.group(1).strip()

        # Extract suggested fix
        fix_match = re.search(r'SUGGESTED_FIX:\s*(.+?)(?=\n[A-Z_]+:|$)', response, re.DOTALL)
        if fix_match:
            result["suggested_fix"] = fix_match.group(1).strip()

        # Extract replacement packages if provided
        replace_match = re.search(r'REPLACEMENT_PACKAGES:\s*(.+)', response)
        if replace_match:
            replacements = [p.strip() for p in replace_match.group(1).split(',')]
            # Create modified config with replacements
            result["modified_config"] = self._apply_package_replacements(
                original_config,
                replacements
            )

        return result

    def _apply_package_replacements(self, config: Dict[str, Any], new_packages: List[str]) -> Dict[str, Any]:
        """Apply suggested package replacements to config"""
        modified = config.copy()
        modified['packages'] = new_packages
        return modified


def suggest_alternative_packages(package_name: str) -> List[str]:
    """
    Suggest alternative package names for common typos/mistakes
    """
    alternatives = {
        "chrome": ["chromium", "firefox-esr"],
        "vscode": ["code-oss"],
        "python": ["python3"],
        "nodejs": ["nodejs"],
        "node": ["nodejs"],
        "npm": ["npm"],
    }

    package_lower = package_name.lower()
    return alternatives.get(package_lower, [])
