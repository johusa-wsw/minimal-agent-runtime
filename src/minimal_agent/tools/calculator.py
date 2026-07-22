from __future__ import annotations

import ast
import math
import operator
from typing import Any, Callable, ClassVar

from pydantic import Field, field_validator

from minimal_agent.tools.base import (
    BaseTool,
    ToolArguments,
    ToolContext,
    ToolExecutionError,
)


class CalculatorArguments(ToolArguments):
    expression: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "需要计算的数学表达式，例如 "
            "'2 + 3 * 4'、'(10 - 2) / 4'"
        ),
    )

    @field_validator("expression")
    @classmethod
    def expression_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Expression cannot be blank")

        return value


class SafeExpressionEvaluator(ast.NodeVisitor):
    """只允许有限数学语法的 AST 计算器。

    禁止函数调用、变量访问、属性访问、导入以及其他 Python 语法。
    """

    BINARY_OPERATORS: ClassVar[
        dict[type[ast.operator], Callable[[Any, Any], Any]]
    ] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    UNARY_OPERATORS: ClassVar[
        dict[type[ast.unaryop], Callable[[Any], Any]]
    ] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    MAX_AST_NODES = 64
    MAX_ABSOLUTE_VALUE = 1_000_000_000_000_000
    MAX_EXPONENT = 12

    def evaluate(self, expression: str) -> int | float:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ToolExecutionError(
                "Invalid mathematical expression syntax"
            ) from exc

        node_count = sum(1 for _ in ast.walk(tree))

        if node_count > self.MAX_AST_NODES:
            raise ToolExecutionError(
                "Expression is too complex"
            )

        result = self.visit(tree)
        return self._validate_number(result)

    def visit_Expression(
        self,
        node: ast.Expression,
    ) -> int | float:
        return self.visit(node.body)

    def visit_Constant(
        self,
        node: ast.Constant,
    ) -> int | float:
        value = node.value

        # bool 是 int 的子类，因此需要单独排除。
        if isinstance(value, bool):
            raise ToolExecutionError(
                "Boolean values are not supported"
            )

        if not isinstance(value, (int, float)):
            raise ToolExecutionError(
                "Only numeric constants are supported"
            )

        return self._validate_number(value)

    def visit_BinOp(
        self,
        node: ast.BinOp,
    ) -> int | float:
        operator_type = type(node.op)
        operation = self.BINARY_OPERATORS.get(operator_type)

        if operation is None:
            raise ToolExecutionError(
                f"Unsupported binary operator: "
                f"{operator_type.__name__}"
            )

        left = self.visit(node.left)
        right = self.visit(node.right)

        if isinstance(node.op, ast.Pow):
            if abs(right) > self.MAX_EXPONENT:
                raise ToolExecutionError(
                    f"Exponent cannot exceed "
                    f"{self.MAX_EXPONENT}"
                )

        try:
            result = operation(left, right)
        except ZeroDivisionError as exc:
            raise ToolExecutionError(
                "Division by zero is not allowed"
            ) from exc
        except OverflowError as exc:
            raise ToolExecutionError(
                "Calculation result is too large"
            ) from exc

        return self._validate_number(result)

    def visit_UnaryOp(
        self,
        node: ast.UnaryOp,
    ) -> int | float:
        operator_type = type(node.op)
        operation = self.UNARY_OPERATORS.get(operator_type)

        if operation is None:
            raise ToolExecutionError(
                f"Unsupported unary operator: "
                f"{operator_type.__name__}"
            )

        operand = self.visit(node.operand)
        result = operation(operand)

        return self._validate_number(result)

    def generic_visit(self, node: ast.AST) -> Any:
        raise ToolExecutionError(
            f"Unsupported expression node: "
            f"{type(node).__name__}"
        )

    def _validate_number(
        self,
        value: Any,
    ) -> int | float:
        if isinstance(value, bool):
            raise ToolExecutionError(
                "Boolean values are not supported"
            )

        if not isinstance(value, (int, float)):
            raise ToolExecutionError(
                "Expression did not produce a real number"
            )

        if isinstance(value, float) and not math.isfinite(value):
            raise ToolExecutionError(
                "Calculation produced a non-finite number"
            )

        if abs(value) > self.MAX_ABSOLUTE_VALUE:
            raise ToolExecutionError(
                "Calculation result exceeds the allowed range"
            )

        return value


class CalculatorTool(BaseTool):
    name = "calculator"

    description = (
        "计算一个数学表达式。支持加、减、乘、除、整除、"
        "取模、幂、括号和一元正负号。"
    )

    args_model = CalculatorArguments

    def __init__(self) -> None:
        self._evaluator = SafeExpressionEvaluator()

    def run(
        self,
        arguments: ToolArguments,
        context: ToolContext | None = None,
    ) -> dict[str, int | float | str]:
        if not isinstance(arguments, CalculatorArguments):
            raise TypeError(
                "CalculatorTool received invalid argument type"
            )

        value = self._evaluator.evaluate(arguments.expression)

        return {
            "expression": arguments.expression,
            "value": value,
            "display": self._format_value(value),
        }

    @staticmethod
    def _format_value(value: int | float) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))

        return str(value)