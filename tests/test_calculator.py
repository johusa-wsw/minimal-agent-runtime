import pytest
from pydantic import ValidationError

from minimal_agent.tools.base import ToolExecutionError
from minimal_agent.tools.calculator import CalculatorTool


@pytest.fixture
def calculator() -> CalculatorTool:
    return CalculatorTool()


def test_calculator_obeys_operator_precedence(
    calculator: CalculatorTool,
) -> None:
    result = calculator.execute(
        {"expression": "2 + 3 * 4"}
    )

    assert result["value"] == 14
    assert result["display"] == "14"


def test_calculator_supports_parentheses(
    calculator: CalculatorTool,
) -> None:
    result = calculator.execute(
        {"expression": "(2 + 3) * 4"}
    )

    assert result["value"] == 20


def test_calculator_supports_unary_operator(
    calculator: CalculatorTool,
) -> None:
    result = calculator.execute(
        {"expression": "-3 + 10"}
    )

    assert result["value"] == 7


def test_calculator_supports_float_result(
    calculator: CalculatorTool,
) -> None:
    result = calculator.execute(
        {"expression": "5 / 2"}
    )

    assert result["value"] == 2.5
    assert result["display"] == "2.5"


def test_calculator_rejects_function_call(
    calculator: CalculatorTool,
) -> None:
    with pytest.raises(
        ToolExecutionError,
        match="Unsupported expression node",
    ):
        calculator.execute(
            {
                "expression": (
                    "__import__('os').system('echo hacked')"
                )
            }
        )


def test_calculator_rejects_variable_name(
    calculator: CalculatorTool,
) -> None:
    with pytest.raises(
        ToolExecutionError,
        match="Unsupported expression node",
    ):
        calculator.execute(
            {"expression": "secret_value + 1"}
        )


def test_calculator_rejects_division_by_zero(
    calculator: CalculatorTool,
) -> None:
    with pytest.raises(
        ToolExecutionError,
        match="Division by zero",
    ):
        calculator.execute(
            {"expression": "10 / 0"}
        )


def test_calculator_rejects_large_exponent(
    calculator: CalculatorTool,
) -> None:
    with pytest.raises(
        ToolExecutionError,
        match="Exponent cannot exceed",
    ):
        calculator.execute(
            {"expression": "2 ** 100"}
        )


def test_calculator_rejects_empty_expression(
    calculator: CalculatorTool,
) -> None:
    with pytest.raises(ValidationError):
        calculator.execute(
            {"expression": "   "}
        )


def test_calculator_rejects_extra_arguments(
    calculator: CalculatorTool,
) -> None:
    with pytest.raises(ValidationError):
        calculator.execute(
            {
                "expression": "1 + 1",
                "dangerous_option": True,
            }
        )